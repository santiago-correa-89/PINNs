import tensorflow as tf
import numpy as np
import time
import datetime
import matplotlib.pyplot as plt
import os

from utilities import *
from classNavierStoke import *

class postProcesisng:
    def __init__(self, XdataTrain, UdataTrain, Xphisic, Xtest, Utest, layers, lr, Re, alpha, folder):

    predict = self.net_u(x_tf, y_tf, t_tf, W, b).numpy()
    phi = predict[:, 0:1]
    p = predict[:, 1:2]
    
    def evalNN(X, W, b):
        x_tf = X[:, 0:1]
        y_tf = X[:, 1:2]
        t_tf = X[:, 2:3]
    

    
    return phi, p

# Load Error 
error = np.load(r"src/results/40Samples_Norm/error.npy")
Xtest = np.load(r"src/results/40Samples_Norm/Xtest.npy")

# Load Data Xdata refers to spacial position of point, Udata is the Velocity field and Pressure fields for the points. 
W = myLoad(r"src/results/40Samples_Norm/wResult1292257")
b = myLoad(r"src/results/40Samples_Norm/bResult1292257")
loss = myLoad(r"src/results/40Samples_Norm/lossResult1292257")
lossU = myLoad(r"src/results/40Samples_Norm/lossUResult1292257")
lossV = myLoad(r"src/results/40Samples_Norm/lossVResult1292257")
lossP = myLoad(r"src/results/40Samples_Norm/lossPResult1292257")
lossF = myLoad(r"src/results/40Samples_Norm/lossFResult1292257")

x = np.arange(-5, 15, 0.1)
y = np.arange(-5, 5, 0.05)
t = np.arange(0, 2, 0.01)

grid = arangeData(x, y, t)
grid_tf = tf.convert_to_tensor(grid, dtype=tf.float32)
phiPred, pPred = evalNN(grid_tf, W, b)

date = str(datetime.datetime.now().month)+str(datetime.datetime.now().day)+str(datetime.datetime.now().hour)+str(datetime.datetime.now().minute)

for k in range(t.shape[0]):
    
    timeEvalMin = k*x.shape[0]*y.shape[0]
    timeEvalMax = timeEvalMin + x.shape[0]*y.shape[0]
    
    grads = np.gradient(phiPred[timeEvalMin:timeEvalMax].reshape((x.shape[0],y.shape[0])))
    u = grads[1]
    v = -grads[0]
    p = pPred[timeEvalMin:timeEvalMax].reshape((x.shape[0],y.shape[0]))
    
    fig, ax = plt.subplots()  
    hm = ax.imshow(p.T, extent=[x.min(), x.max(), y.min(), y.max()])
    animation(hm, r"src/results/40Samples_Norm/pEstimation/presion", k, 'Pressure Field') 
    plt.close()
    
    # fig, ax = plt.subplots()
    # hm, _, _, gridErrorP  = nonuniform_imshow(Xtest[:, 0], Xtest[:, 1], np.vstack(error[2, :]))
    # animation(hm, r"src/data/fig/presionEstimation/errPresion", k, 'Error Pressure Field')
    # plt.close() 
    
    fig, ax = plt.subplots()  
    hm = ax.imshow(u.T, extent=[x.min(), x.max(), y.min(), y.max()])
    animation(hm, r"src/results/40Samples_Norm/uEstimation/u", k, 'U Field') 
    plt.close()
    
    # fig, ax = plt.subplots()
    # hm, _, _, gridErrorU  = nonuniform_imshow(Xtest[:, 0], Xtest[:, 1], np.vstack(error[0, :]))
    # animation(hm, r"src/data/fig/uEstimation/errorU", k, 'Error U Field') 
    # plt.close()
        
    fig, ax = plt.subplots()  
    hm = ax.imshow(v.T, extent=[x.min(), x.max(), y.min(), y.max()])
    animation(hm, r"src/results/40Samples_Norm/vEstimation/v", k, 'V Field') 
    plt.close()
    
    # fig, ax = plt.subplots()
    # hm, _, _, gridErrorV  = nonuniform_imshow(Xtest[:, 0], Xtest[:, 1], np.vstack(error[1, :]))
    # animation(hm, r"src/data/fig/vEstimation/errorV", k, 'Error V Field') 
    # plt.close()

videoCreater(r"src/results/40Samples_Norm/pEstimation/presion", r"src/results/40Samples_Norm/pEstimation/presion" + str(date) + ".avi", t.shape[0])
videoCreater(r"src/results/40Samples_Norm/uEstimation/u", r"src/results/40Samples_Norm/uEstimation/u" + str(date) + ".avi", t.shape[0])
videoCreater(r"src/results/40Samples_Norm/vEstimation/v", r"src/results/40Samples_Norm/vEstimation/v" + str(date) + ".avi", t.shape[0])
# videoCreater(r"src/data/fig/presionEstimation/presion", r"src/data/fig/presionEstimation/errorPresion" + str(date) + ".avi", t.shape[0])
# videoCreater(r"src/data/fig/uEstimation/u", r"src/data/fig/uEstimation/errorU" + str(date) + ".avi", t.shape[0])
# videoCreater(r"src/data/fig/vEstimation/v", r"src/data/fig/vEstimation/errorV" + str(date) + ".avi", t.shape[0])

# for k in range(t.shape[0]):
    # os.remove(r"src/data/fig/presionEstimation/presion" + str(k) + ".png")
    # os.remove(r"src/data/fig/uEstimation/u" + str(k) + ".png")
    # os.remove(r"src/data/fig/vEstimation/v" + str(k) + ".png")
    
    # os.remove(r"src/data/fig/presionEstimation/errPresion" + str(k) + ".png")
    # os.remove(r"src/data/fig/uEstimation/errorU" + str(k) + ".png")
    # os.remove(r"src/data/fig/vEstimation/errorV" + str(k) + ".png")

folder = r'src/results/test'

fig = plt.figure()
ax = fig.add_subplot(111)
ax.plot(lossF, 'r--', (lossU+lossV+lossP), 'k^', loss, 'bs')
ax.set_xlabel('$n iter$')
ax.set_ylabel('Loss')
plt.yscale('log')
ax.set_title('Loss evolution 40 Data Samples Normalized', fontsize = 10)
fig.show()

fig = plt.figure()
ax = fig.add_subplot(111)
ax.plot(lossF, 'r--', lossU, 'k^', lossV, 'r^', lossP, 'b^', loss, 'bs')
ax.set_xlabel('$n iter$')
ax.set_ylabel('Loss')
plt.yscale('log')
ax.set_title('Loss evolution 40 Data Samples Normalized', fontsize = 10)
fig.show()