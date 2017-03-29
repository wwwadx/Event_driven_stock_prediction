####this file is used to do word2vec#########
from gensim.models import Word2Vec
import pandas as pd
import nltk 
import re 
from sentiment import parse_1, date_transform
import os
import sys
import operator
import numpy as np

from sklearn import model_selection, preprocessing, ensemble
from sklearn.feature_extraction.text import TfidfVectorizer
from scipy.stats import zscore
from keras.models import Sequential
from keras.layers import Dense, Dropout, Activation
from keras.layers.normalization import BatchNormalization
from keras.layers.advanced_activations import PReLU
from keras.callbacks import EarlyStopping, ModelCheckpoint
from sklearn.metrics import accuracy_score
def trainset(df):
	all_sentence=[]
	for i in range(df.shape[0]):
		sentence=[]
		for j in range(df.shape[1]):
			string=str(df.iloc[i,j])
			if len(string)!=0:
				sentence+=string.split(' ')
		all_sentence.append(sentence)
	return all_sentence

def all_trainset():
	TickerList=["AA","AAPL","ABT","AMAT","BAC","BBBY","C","CAT","CHK","D","DOW","F","FCX","GE","JNJ","JNPR","K",\
			"KO","LLY","LMT","MCD","PG","PPL","RF","SLB","SO","T","VOD","VZ","XOM"]
	all_trainset=[]
	for ticker in TickerList:
		data=pd.read_csv('../data/reverb/'+ticker+'reverb.csv',header=0)
		df=data.loc[:,['subject','object','verb']].fillna('')
		all_trainset+=trainset(df)
	return all_trainset

def TSdf(market_data):#time series lag 5 data
	return_=[]
	for i in range(market_data.shape[0]-1):
		return_.append(market_data.iloc[i+1,1]/market_data.iloc[i,1]-1.0)
	date=market_data.Date[1:]
	df={}
	return_5=return_[:-5]
	return_4=return_[1:-4]
	return_3=return_[2:-3]
	return_2=return_[3:-2]
	return_1=return_[4:-1]
	return_y=return_[5:]
	df['return_5']=return_5
	df['return_4']=return_4
	df['return_3']=return_3
	df['return_2']=return_2
	df['return_1']=return_1
	df['return_y']=map(lambda x: 1 if x>=0 else 0,return_y)
	df['Date']=date[5:]
	dataframe=pd.DataFrame(df)
	common_data=pd.read_csv('../data/Price/common_data.csv',header=0)
	final=dataframe.merge(common_data,how='left',on='Date')
	return final

def main():
	print "This is word2vec with Neural Network training.\n"
	ticker=raw_input("please input ticker")
	train_set=all_trainset()
	data=pd.read_csv('../data/reverb/'+ticker+'reverb.csv',header=0)
	data['Date']=data.date
	df=data.loc[:,['subject','object','verb']].fillna('')
	test_set=trainset(df)
	model = Word2Vec(train_set, min_count=1,window=4,size=100,workers=4)
	print "word2vec model created"
	AllLis=[]
	for each in train_set:
		lis=[0]*100
		if len(each)!=0:
			for each_word in each:
				lis+=model.wv[each_word]
			lis/=len(each)
		AllLis.append(lis)
	vectors=pd.DataFrame(AllLis)
	vectors['Date']=date_transform(data).Date
	market_data=pd.read_csv('../data/Price/'+ticker+'.csv',header=0)
	TSdf_=TSdf(market_data)
	final=TSdf_.merge(vectors,how='left',on='Date').fillna(0)
	final.drop('Date',axis=1,inplace=True)
	print "final dataset created"
	print "final columns are ", final.columns
	y_test,pred_test=NN(final,300,50,ticker,"Word2VecAll")

def NN(df,fir,sec,ticker,folder):
	traintest=df.ix[:, df.columns != 'return_y']
	y=df.loc[:,'return_y']
	train_size=int(0.8*traintest.shape[0])
	x_train=traintest.iloc[-train_size:,:]
	x_test=traintest.iloc[:(traintest.shape[0]-train_size),:]
	y_train=y.iloc[-train_size:]
	y_test=y.iloc[:(traintest.shape[0]-train_size)]
	train_X = x_train.as_matrix()
	test_X = x_test.as_matrix()
	print "before scalar train size",train_X.shape
	print "before scalar test size",test_X.shape

	traintest = np.vstack((train_X, test_X))

	traintest = preprocessing.StandardScaler().fit_transform(traintest)

	train_X = traintest[range(train_X.shape[0])]
	test_X = traintest[range(train_X.shape[0], traintest.shape[0])]
	print "after scalar train size",train_X.shape
	print "after scalar test size", test_X.shape
	## neural net
	def nn_model():
		model = Sequential()   
		model.add(Dense(fir, input_dim = train_X.shape[1], init = 'he_normal', activation='tanh'))
		model.add(BatchNormalization())
		model.add(PReLU())  
		model.add(Dense(sec, init = 'he_normal', activation='tanh'))
		model.add(BatchNormalization())    
		model.add(PReLU())	
		model.add(Dense(1, init = 'he_normal', activation='sigmoid'))
		model.compile(loss = 'binary_crossentropy', optimizer = 'adam')#, metrics=['accuracy'])
		return(model)
	train_y = y_train
	print "this is train Y",train_y
	print '-'*50
	do_all = True
	## cv-folds
	nfolds = 1
	print "model created then fold"
	
	testset = test_X
	ytestset = y_test


	## train models
	nbags = 5

	from time import time
	import datetime

	pred_test = np.zeros([testset.shape[0],1])
	begintime = time()
	count = 0
	filepath="weights.best.hdf5"
	print "-"*100
	print "Start train"
	print "-"*100
	pred_train=np.zeros([x_train.shape[0],1])
	for j in range(nbags):
		print(j)
		model = nn_model()
		model.fit(train_X, train_y, nb_epoch = 1200, batch_size=100, verbose = 0)
		pred_test += model.predict(x=testset, verbose=0)
		print "pred_test dimension is" , pred_test.shape
		print "testset dimension is" , testset.shape
		pred_train += model.predict(x=train_X,verbose=0)
		print "pred_train dimension is" , pred_train.shape
		print "train_X dimension is" , train_X.shape
		print(str(datetime.timedelta(seconds=time()-begintime)))
	pred_test=pred_test/nbags
	pred_train=pred_train/nbags
	pred_test=map(lambda x: 1 if x>0.5 else 0, pred_test)
	pred_train=map(lambda x: 1 if x>0.5 else 0, pred_train)

	train_result="train accuracy is " +str(accuracy_score(y_train,pred_train))+'\n'
	test_result="test accuracy is "+ str(accuracy_score(y_test, pred_test))

	print train_result
	print test_result
	f=open('../data/'+folder+'/'+ticker+'/'+ticker+'.txt','w')
	f.write(train_result)
	f.write(test_result)
	f.close()
	return y_test,pred_test

main()







