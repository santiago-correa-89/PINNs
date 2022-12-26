import tensorflow as tf
import tensorflow_probability as tfp
import numpy as np
import time
import datetime
import matplotlib.pyplot as plt

from scipy.interpolate import griddata
import matplotlib.pyplot as plt
from PIL import Image 

from scipy import spatial
from pyDOE import lhs

import pickle
import os

from utilities import *
from flatWeightsLBFGS import *

np.random.seed(seed=1234)
tf.random.set_seed(1234)
tf.config.experimental.enable_tensor_float_32_execution(False)

class NavierStoke:
    #Initialize the class
    
    def __init__(self, XdataTrain, UdataTrain, Xphisic, Xtest, Utest, xBC, uBC, layers, lr, Re, alpha, folder, nIterAdam, niterLBFGS):
        
        self.nIterAdam = nIterAdam
        self.niterLBFGS = niterLBFGS
        
        self.alpha = alpha
        self.Re = Re
        self.lb = XdataTrain.min(0)
        self.ub = XdataTrain.max(0)
        
        #Boundary Conditions
        self.xBC = xBC
        self.uBC = uBC
        
        #Training data Points
        self.xTrain_tf = tf.convert_to_tensor(XdataTrain[:, 0:1], dtype=tf.float32)
        self.yTrain_tf = tf.convert_to_tensor(XdataTrain[:, 1:2], dtype=tf.float32)
        self.tTrain_tf = tf.convert_to_tensor(XdataTrain[:, 2:3], dtype=tf.float32)
        self.XdataTrain_tf = tf.convert_to_tensor(XdataTrain, dtype=tf.float32)
        
        #Training data Variables
        self.uTrain = UdataTrain[:, 0:1]
        self.vTrain = UdataTrain[:, 1:2]
        self.pTrain = UdataTrain[:, 2:3]
        self.UdataTrain = tf.convert_to_tensor(UdataTrain, dtype=tf.float32)
        
        #Physics points for training
        self.xPhisic_tf = tf.convert_to_tensor(Xphisic[:, 0:1], dtype=tf.float32)
        self.yPhisic_tf = tf.convert_to_tensor(Xphisic[:, 1:2], dtype=tf.float32)
        self.tPhisic_tf = tf.convert_to_tensor(Xphisic[:, 2:3], dtype=tf.float32)
        self.Xphisics_tf = tf.convert_to_tensor(Xphisic, dtype=tf.float32)
        
        #Test points
        self.xTest_tf = tf.convert_to_tensor(Xtest[:, 0:1], dtype=tf.float32)
        self.yTest_tf = tf.convert_to_tensor(Xtest[:, 1:2], dtype=tf.float32)
        self.tTest_tf = tf.convert_to_tensor(Xtest[:, 2:3], dtype=tf.float32)
        self.XTest_tf = tf.convert_to_tensor(Xtest, dtype=tf.float32)
        
        #Test data for training
        self.uTest = Utest[:, 0:1]
        self.vTest = Utest[:, 1:2]
        self.pTest = Utest[:, 2:3]
        
        #NN structure
        self.layers = layers
        self.W, self.b = self.InitializeNN(self.layers)
        
        #NN first optimizer
        self.optimizer_adam = tf.optimizers.Adam(learning_rate=lr)
        
        start_time = time.time()
        n=0
        self.loss = []
        self.lossU = []
        self.lossF = []

        while n <= self.nIterAdam:
            loss_, lossU_, lossF_, self.W, self.b = self.train_step(self.W, self.b)
            self.loss.append(loss_)
            self.lossU.append(lossU_)
            self.lossF.append(lossF_)   
        
            if(n %100 == 0):   
                print(f"Iteration is: {n} and loss is: {loss_}, {lossF_}, {lossU_}")
            n+=1
        
        # Create the LossAndFlatGradient instance
        loss_and_gradient = LossAndFlatGradient(self.train_vars(self.W, self.b), lambda: self.closureLoss(self.W, self.b))    
        
        # Call lbfgs_minimize to optimize the neural network
        initial_weights = loss_and_gradient.to_flat_weights(self.train_vars(self.W, self.b))
        optimizer = tfp.optimizer.lbfgs_minimize(loss_and_gradient, initial_position=initial_weights, 
        num_correction_pairs=100,
        tolerance=1e-8,
        x_tolerance=0,
        f_relative_tolerance=0,
        max_iterations=self.niterLBFGS,
        parallel_iterations=1,
        max_line_search_iterations=50)
        
        result = optimizer.set_flat_weights(optimizer.position)
        print(optimizer)
        
        elapsed = time.time() - start_time                
        print('Training time: %.4f' % (elapsed))
        
        # Save parameteres for postprocessing
        date = str(datetime.datetime.now().month)+str(datetime.datetime.now().day)+str(datetime.datetime.now().hour)+str(datetime.datetime.now().minute)
    
        mySave(folder + '/wResult' + date, self.W)
        mySave(folder + '/bResult' + date, self.b)
        mySave(folder + '/lossResult' + date, self.loss)
        mySave(folder + '/lossUResult' + date, self.lossU)
        mySave(folder + '/lossFResult' + date, self.lossF)
        
        # Prediction of NN for test points
        self.uPredict, self.vPredict, self.pPredict = self.predict(self.W, self.b)
        
        # Error estimation for prediction of NN
        self.errU = (self.uTest - self.uPredict.numpy())/self.uTest
        self.errV = (self.vTest - self.vPredict.numpy())/self.vTest
        self.errP = (self.pTest - self.pPredict.numpy())/self.pTest
    
        np.save(folder + "/error.npy", [self.errU, self.errV, self.errP])
    
        self.meanErrorU = np.mean(np.abs(self.errU))*100 
        self.meanErrorV = np.mean(np.abs(self.errV))*100
        self.meanErrorP = np.mean(np.abs(self.errP))*100
    
        np.save(folder + '/Xtest.npy', Xtest)
    
        print("Percentual errors are {:.2f} in u, {:.2f} in v and {:.2f} in p.".format(self.meanErrorU, self.meanErrorV, self.meanErrorP))
        
        fig = plt.figure()
        ax = fig.add_subplot(111)
        ax.plot(self.lossF, 'r--', self.lossU, 'k^', self.loss, 'bs')
        ax.set_xlabel('$n iter$')
        ax.set_ylabel('Loss')
        plt.yscale('log')
        ax.set_title('Loss evolution', fontsize = 10)
        fig.show()
    
    # Initalization of Network
    def hyper_initial(self, size):
        in_dim = size[0]
        out_dim = size[1]
        std = np.sqrt(2.0/(in_dim + out_dim))
        return tf.Variable(tf.random.truncated_normal(shape=size, stddev = std))
    
    def InitializeNN(self, layers):
        L = len(layers)
        W = [self.hyper_initial([layers[l-1], layers[l]]) for l in range(1, L)] 
        b = [tf.Variable(tf.zeros([1, layers[l]])) for l in range(1, L)]
        return W, b

    # Neural Network 
    def DNN(self, X, W, b):
        A = 2.0*(X - self.lb)/(self.ub - self.lb) - 1.0   
        L = len(W)
        for i in range(L-1):
            A = tf.tanh(tf.add(tf.matmul(A, W[i]), b[i]))
            Y = tf.add(tf.matmul(A, W[-1]), b[-1])
        return Y

    def train_vars(self, W, b):
        return W + b

    def net_u(self, x, y, t, w, b):
        output  = self.DNN(tf.concat([x, y, t], 1), w, b)
        return output

    def net_f(self, x, y, t, W, b):
        with tf.GradientTape(persistent=True) as tape1:
            tape1.watch([x, y, t])
        
            with tf.GradientTape(persistent=True) as tape2:
                tape2.watch([x, y, t])
            
                with tf.GradientTape(persistent=True) as tape3:
                    tape3.watch([x, y, t])
                    output = self.net_u(x, y, t, W, b)
                    psi = output[:,0:1]
                    p = output[:,1:2]
                    wz = output[:, 2:3]
       
                u = tape3.gradient(psi, y)
                v = -tape3.gradient(psi, x)
    
            u_x = tape2.gradient(u, x)
            u_y = tape2.gradient(u, y)
            u_t = tape2.gradient(u, t)
            v_x = tape2.gradient(v, x)
            v_y = tape2.gradient(v, y)
            v_t = tape2.gradient(v, t)
            p_x = tape2.gradient(p, x)
            p_y = tape2.gradient(p, y)
    
        u_xx = tape1.gradient(u_x, x)
        u_yy = tape1.gradient(u_y, y)
        v_xx = tape1.gradient(v_x, x)
        v_yy = tape1.gradient(v_y, y)
    
        del tape1
    
        fx = u_t + (u*u_x + v*u_y) + p_x - self.Re*(u_xx + u_yy)
        fy = v_t + (u*v_x + v*v_y) + p_y - self.Re*(v_xx + v_yy)
        return fx, fy

    def train_step(self, W, b):
        with tf.GradientTape(persistent=True) as tape4:
            tape4.watch([W, b])
        
            with tf.GradientTape(persistent=True) as tape5:
                tape5.watch([self.xTrain_tf, self.yTrain_tf, self.tTrain_tf])
                output = self.net_u(self.xTrain_tf, self.yTrain_tf, self.tTrain_tf, W, b)
                psi = output[:, 0:1]
                p = output[:, 1:2]
       
            u = tape5.gradient(psi, self.yTrain_tf)
            v = -tape5.gradient(psi, self.xTrain_tf)
            del tape5    
        
            fx, fy = self.net_f(self.xPhisic_tf, self.yPhisic_tf, self.tPhisic_tf, W, b)
            
            lossU = tf.reduce_mean(tf.square(u - self.uTrain)) \
            + tf.reduce_mean(tf.square(v - self.vTrain)) \
            + tf.reduce_mean(tf.square(p - self.pTrain))
                    
            lossF = tf.reduce_mean(tf.square( fx )) + tf.reduce_mean(tf.square( fy ))
            
            loss = self.alpha*(lossU) + (1 - self.alpha)*lossF
        
        grads = tape4.gradient(loss, self.train_vars(W,b))
        self.optimizer_adam.apply_gradients(zip(grads, self.train_vars(W,b)))
        del tape4
        
        return loss, lossU, lossF, W, b
    
    def predict(self, W, b):
    
        with tf.GradientTape(persistent=True) as tape6:
            tape6.watch([self.xTest_tf, self.yTest_tf, self.tTest_tf])
            output = self.net_u(self.xTest_tf, self.yTest_tf, self.tTest_tf, W, b)
            psi = output[:,0:1]
            p = output[:,1:2]
       
        u = tape6.gradient(psi, self.yTest_tf)
        v = -tape6.gradient(psi, self.xTest_tf)
        return u, v, p
    
    def evalNN(self, X, W, b):
        x_tf = X[:, 0:1]
        y_tf = X[:, 1:2]
        t_tf = X[:, 2:3]
    
        predict = self.net_u(x_tf, y_tf, t_tf, W, b).numpy()
        phi = predict[:, 0:1]
        p = predict[:, 1:2]
    
        return phi, p
    
    def closureLoss(self, W, b):
        
            with tf.GradientTape(persistent=True) as tape7:
                tape7.watch([self.xTrain_tf, self.yTrain_tf, self.tTrain_tf])
                output = self.net_u(self.xTrain_tf, self.yTrain_tf, self.tTrain_tf, W, b)
                psi = output[:, 0:1]
                p = output[:, 1:2]
       
            u = tape7.gradient(psi, self.yTrain_tf)
            v = -tape7.gradient(psi, self.xTrain_tf)
            del tape7    
        
            fx, fy = self.net_f(self.xPhisic_tf, self.yPhisic_tf, self.tPhisic_tf, W, b)
            
            #Training Loss
            lossU = tf.reduce_mean(tf.square(u - self.uTrain_tf))
            lossV = tf.reduce_mean(tf.square(v - self.vTrain_tf))
            lossP = tf.reduce_mean(tf.square(p - self.pTrain_tf))

            #Training BC
            lossBC = tf.reduce_mean(tf.square( - self.uTrain_tf))
            
            lossF = tf.reduce_mean(tf.square( fx )) + tf.reduce_mean(tf.square( fy ))    
            
            loss = self.alpha*(lossU + lossV + lossP) + (1 - self.alpha)*lossF
        
            return loss
        
    # def lbfgs_minimizeNS(self, trainable_variables, build_loss, previous_optimizer_results=None):
    #     """TensorFlow interface for tfp.optimizer.lbfgs_minimize.
    #     Args:
    #     trainable_variables: Trainable variables, also used as the initial position.
    #     build_loss: A function to build the loss function expression.
    #     previous_optimizer_results
    #     """
    #     func = LossAndFlatGradient(trainable_variables, build_loss)
    #     initial_position = None
    #     if previous_optimizer_results is None:
    #         initial_position = func.to_flat_weights(trainable_variables)
    #         results = tfp.optimizer.lbfgs_minimize(
    #         func,
    #         initial_position=initial_position,
    #         previous_optimizer_results=previous_optimizer_results,
    #         num_correction_pairs = 100,
    #         tolerance = 1e-8,
    #         x_tolerance = 0,
    #         f_relative_tolerance = 0,
    #         max_iterations = self.niterLBFGS,
    #         parallel_iterations = 1,
    #         max_line_search_iterations = 50,
    #     )
    # The final optimized parameters are in results.position.
    # Set them back to the variables.
        # func.set_flat_weights(results)
        # return results

if __name__ == "__main__": 
# Defining variables
    D = 1 
    nu = 0.01
    Uinf = 1
    Re = nu/(Uinf*D)   
    noise = 0.0        
    Ntest = 200
    Ndata = 40
    Nfis = 5000 
    nIterAdam = 5
    niterLBFGS = 5
    T=201
    
    # Defining alpha value
    alpha = 0.7

    # Defining Neural Network
    layers = [3, 20, 20, 20, 20, 20, 20, 20, 20, 2]

    # Load Data Xdata refers to spacial position of point, Udata is the Velocity field and Pressure fields for the points. 
    Xdata = np.load(r"src/data/vorticityTest/Xdata.npy")
    Udata = np.load(r"src/data/vorticityTest/Udata.npy")
    
    # Boundary Conditions
    _, upperBConditionIdx = spatial.KDTree(Xdata).query(Xdata[(Xdata[:,1] == 5)])
    XupBC, UpBC = conform_data(Xdata, Udata, upperBConditionIdx, T=None)

    _, underBConditionIdx = spatial.KDTree(Xdata).query(Xdata[(Xdata[:,1] == .5)])
    XunBC, UnBC = conform_data(Xdata, Udata, underBConditionIdx, T=None)
    
    _, inletBConditionIdx = spatial.KDTree(Xdata).query(Xdata[(Xdata[:,0] == -5)])
    XinBC, InBC = conform_data(Xdata, Udata, inletBConditionIdx, T=None)
    
    xBC = np.concatenate((XunBC, XinBC, XupBC), axis=0, out=None)
    uBC = np.concatenate((UnBC, InBC, UpBC), axis=0, out=None) 

    # Select a number of point to test the NN
    idxTest = select_idx(Xdata, Ntest, criterion='uni')
    Xtest, Utest = conform_data(Xdata, Udata, idxTest)
    Xtest = Xtest[(Utest[:,0]>0.01)*(Utest[:,1]>0.01)*(Utest[:,2]>0.01)] # Filter to avoide data (u, v, p) near zero
    Utest = Utest[(Utest[:,0]>0.01)*(Utest[:,1]>0.01)*(Utest[:,2]>0.01)] # Filter to avoide data (u, v, p) near zero

    # Remove index used for test
    Xdata = np.delete(Xdata, idxTest, axis=0)
    Udata = np.delete(Udata, idxTest, axis=0)
    
    idxTrain = select_idx(Xdata, Ndata, criterion='lhs')
    XdataTrain, UdataTrain = conform_data(Xdata, Udata, idxTrain)
    XdataTrain = np.concatenate((XunBC, XupBC, XinBC, XdataTrain))
    UdataTrain = np.concatenate((UnBC, UpBC, InBC, UdataTrain))
    
    ptsF = np.random.uniform([-5, -5], [15, 5], size=(Nfis, 2))  #interior fis points w no data
    Xphisic = np.c_[ptsF, 0.01*np.random.randint(T, size=Nfis) ]
    Xphisic = np.vstack([Xphisic, circle_points(Nfis)]) #border fis points w no data
    Xphisic = np.vstack([Xphisic, XdataTrain]) #eval fis in data points

    lr = 1e-3
    
    folder = r'src/results/test'
    
    model = NavierStoke(XdataTrain, UdataTrain, Xphisic, Xtest, Utest, xBC, uBC, layers, lr, Re, alpha, folder, nIterAdam, niterLBFGS)