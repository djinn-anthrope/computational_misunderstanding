import os
import time
import load_data
import torch
import torch.nn.functional as F
from torch.autograd import Variable
import torch.optim
import numpy as np
from models.LSTM import LSTMClassifier
from models.LSTM_Attn import AttentionModel

datadir = '/mount/projekte/emmy-noether-roth/mist/misunderstanding/csv' 
test_path = '/home/users2/debnatak/computational_misunderstanding/Experiments/data/test_files.txt'
val_path = '/home/users2/debnatak/computational_misunderstanding/Experiments/data/dev_files.txt'

train_df, test_df, val_df = load_data.create_dataset_from_csv(datadir, test_path, val_path)
TEXT, vocab_size, word_embeddings, train_iter, valid_iter, test_iter = load_data.load_dataset(train_df, test_df, val_df)

def clip_gradient(model, clip_value):
    params = list(filter(lambda p: p.grad is not None, model.parameters()))
    for p in params:
        p.grad.data.clamp_(-clip_value, clip_value)
    
def train_model(model, train_iter, epoch):
    total_epoch_loss = 0
    total_epoch_acc = 0
    model.cuda()
    optim = torch.optim.Adam(filter(lambda p: p.requires_grad, model.parameters()))
    steps = 0
    model.train()
    for idx, batch in enumerate(train_iter):
        text = batch.text[0]
        target = batch.label
        target = torch.autograd.Variable(target).long()
        if torch.cuda.is_available():
            text = text.cuda()
            target = target.cuda()
        if (text.size()[0] != 32):# One of the batch returned by BucketIterator has length different than 32.
            continue
        optim.zero_grad()
        prediction = model(text)
        loss = loss_fn(prediction, target)
        num_corrects = (torch.max(prediction, 1)[1].view(target.size()).data == target.data).float().sum()
        acc = 100.0 * num_corrects/len(batch)
        loss.backward()
        clip_gradient(model, 0.1)
        optim.step()
        steps += 1
        
        if steps % 1000 == 0:
            print (f'Epoch: {epoch+1}\t|\tIdx: {idx+1}\t|\tTraining Loss: {loss.item():.4f}\t|\tTraining Accuracy: {acc.item(): .2f}%')
        total_epoch_loss += loss.item()
        total_epoch_acc += acc.item()
        
    return total_epoch_loss/len(train_iter), total_epoch_acc/len(train_iter)

def eval_model(model, val_iter):
    total_epoch_loss = 0
    total_epoch_acc = 0
    model.eval()
    with torch.no_grad():
        for idx, batch in enumerate(val_iter):
            text = batch.text[0]
            if (text.size()[0] != 32):
                continue
            target = batch.label
            target = torch.autograd.Variable(target).long()
            if torch.cuda.is_available():
                text = text.cuda()
                target = target.cuda()
            prediction = model(text)
            loss = loss_fn(prediction, target)
            num_corrects = (torch.max(prediction, 1)[1].view(target.size()).data == target.data).sum()
            acc = 100.0 * num_corrects/len(batch)
            total_epoch_loss += loss.item()
            total_epoch_acc += acc.item()

    return total_epoch_loss/len(val_iter), total_epoch_acc/len(val_iter)
	

learning_rate = 2e-5
batch_size = 32
output_size = 2
hidden_size = 256
embedding_length = 300

model = LSTMClassifier(batch_size, output_size, hidden_size, vocab_size, embedding_length, word_embeddings)
model = AttentionModel(batch_size, output_size, hidden_size, vocab_size, embedding_length, word_embeddings)
loss_fn = F.cross_entropy

for epoch in range(10000):
    train_loss, train_acc = train_model(model, train_iter, epoch)
    val_loss, val_acc = eval_model(model, valid_iter)
    print('-' * 112)
    print(f'Epoch: {epoch+1:02}\t|\tTrain Loss: {train_loss:.3f}\t|\tTrain Acc: {train_acc:.2f}%\t|\tVal. Loss: {val_loss:3f}\t|\tVal. Acc: {val_acc:.2f}%')
    print('=' * 112)

test_loss, test_acc = eval_model(model, test_iter)
print(f'Test Loss: {test_loss:.3f}, Test Acc: {test_acc:.2f}%')

''' Let us now predict the sentiment on a single sentence just for the testing purpose. '''
test_sen1 = "Make rooms for the thing."
test_sen2 = "Construct the rooms for your castle."

test_sen1 = TEXT.preprocess(test_sen1)
test_sen1 = [[TEXT.vocab.stoi[x] for x in test_sen1]]

test_sen2 = TEXT.preprocess(test_sen2)
test_sen2 = [[TEXT.vocab.stoi[x] for x in test_sen2]]

with torch.no_grad():
    test_sen = np.asarray(test_sen1)
    test_sen = torch.LongTensor(test_sen)
    test_tensor = Variable(test_sen, volatile=True)
    test_tensor = test_tensor.cuda()
    model.eval()
    output = model(test_tensor, 1)
    out = F.softmax(output, 1)
    if (torch.argmax(out[0]) == 0):
        print ("Category: Source")
    else:
        print ("Category: Target")
