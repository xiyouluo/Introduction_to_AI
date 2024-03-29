from typing import List
import math
import numpy as np
from .Init import * 

def shape(x):
    if isinstance(x, np.ndarray):
        ret = "ndarray"
        if np.any(np.isposinf(x)):
            ret += "_posinf"
        if np.any(np.isneginf(x)):
            ret += "_neginf"
        if np.any(np.isnan(x)):
            ret += "_nan"
        return f" {x.shape} "
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        ret = "float"
        if np.any(np.isposinf(x)):
            ret += "_posinf"
        if np.any(np.isneginf(x)):
            ret += "_neginf"
        if np.any(np.isnan(x)):
            ret += "_nan"
        return ret
    else:
        raise NotImplementedError(f"unsupported type {type(x)}")

class Node(object):
    def __init__(self, name, *params):
        # 节点的梯度，self.grad[i]对应self.params[i]
        self.grad = []
        # 节点保存的临时数据
        self.cache = []
        # 节点的名字
        self.name = name
        # 用于Linear节点中存储weight和bias参数使用
        self.params = list(params)

    def num_params(self):
        return len(self.params)

    def cal(self, X):
        '''
        计算函数值
        '''
        pass

    def backcal(self, grad):
        '''
        计算梯度
        '''
        pass

    def flush(self):
        # 初始化/刷新
        self.grad = []
        self.cache = []

    def forward(self, x, debug=False):
        '''
        正向传播
        '''
        if debug:
            print(self.name, shape(x))
        ret = self.cal(x)
        if debug:
            print(shape(ret))
        return ret

    def backward(self, grad, debug=False):
        '''
        反向传播
        '''
        if debug:
            print(self.name, shape(grad))
        ret = self.backcal(grad)
        if debug:
            print(shape(ret))
        return ret
    
    def eval(self):
        pass

    def train(self):
        pass


class relu(Node):
    # shape x: (*)
    # shape value: (*) relu(x)
    def __init__(self):
        super().__init__("relu")

    def cal(self, x):
        self.cache.append(x)
        return np.clip(x, 0, None)

    def backcal(self, grad):
        return np.multiply(grad, self.cache[-1] > 0) 

class sigmoid(Node):
    # shape x: (*)
    # shape value: (*) sigmoid(x)
    def __init__(self):
        super().__init__("sigmoid")

    def cal(self, X):
        # TODO: YOUR CODE HERE
        ret = 1 / (1 + np.exp(-X))
        self.cache.append(ret)
        return ret

    def backcal(self, grad):
        # TODO: YOUR CODE HERE
        sigmoid_X = self.cache[-1]
        return np.multiply(grad, np.multiply(sigmoid_X, (1 - sigmoid_X)))        

class tanh(Node):
    # shape x: (*)
    # shape value: (*) tanh(x)
    def __init__(self):
        super().__init__("tanh")

    def cal(self, x):
        ret = np.tanh(x)
        self.cache.append(ret)
        return ret

    def backcal(self, grad):
        return np.multiply(grad, np.multiply(1+self.cache[-1], 1-self.cache[-1]))
    
class Linear(Node):
    # shape x: (*,d1)
    # shape weight: (d1, d2)
    # shape bias: (d2)
    # shape value: (*, d2) 
    def __init__(self, indim, outdim):
        """
        初始化
        @param indim: 输入维度
        @param outdim: 输出维度
        """
        weight = kaiming_uniform(indim, outdim)
        bias = zeros(outdim)
        super().__init__("linear", weight, bias)

    def cal(self, X):
        # TODO: YOUR CODE HERE
        self.cache.append(X)
        return np.dot(X, self.params[0]) + self.params[1]

    def backcal(self, grad):
        # TODO: YOUR CODE HERE
        X = self.cache[-1]
        self.grad.append(np.dot(X.T, grad))
        self.grad.append(np.sum(grad, axis=0))
        return np.dot(grad, self.params[0].T)

class StdScaler(Node):
    '''
    input shape (*)
    output shape (*)
    '''
    EPS = 1e-3
    def __init__(self, mean, std):
        super().__init__("StdScaler")
        self.mean = mean
        self.std = std

    def cal(self, X):
        X = X.copy()
        X -= self.mean
        X /= (self.std + self.EPS)
        return X

    def backcal(self, grad):
        return grad/ (self.std + self.EPS)
    
class BatchNorm(Node):
    '''
    input shape (*)
    output shape (*)
    '''
    EPS = 1e-3
    def __init__(self, indim, momentum: float = 0.9):
        super().__init__("batchnorm", ones((indim)), zeros(indim))
        self.momentum = momentum
        self.mean = None
        self.std = None
        self.updatemean = True
        self.indim = indim

    def cal(self, X):
        if self.updatemean:
            tmean, tstd = np.mean(X, axis=0, keepdims=True), np.std(X, axis=0, keepdims=True)
            if self.std is None or self.std is None:
                self.mean = tmean
                self.std = tstd
            else:
                self.mean *= self.momentum
                self.mean += (1-self.momentum) * tmean
                self.std *= self.momentum
                self.std += (1-self.momentum) * tstd
        X = X.copy()
        X -= self.mean
        X /= (self.std + self.EPS)
        self.cache.append(X.copy())
        X *= self.params[0]
        X += self.params[1]
        return X

    def backcal(self, grad):
        X = self.cache[-1]
        self.grad.append(np.multiply(X, grad).reshape(-1, self.indim).sum(axis=0))
        self.grad.append(grad.reshape(-1, self.indim).sum(axis=0))
        return (grad*self.params[0])/ (self.std + self.EPS)
    
    def eval(self):
        self.updatemean = False

    def train(self):
        self.updatemean = True

class Dropout(Node):
    '''
    input shape (*)
    output shape (*)
    '''
    def __init__(self, p: float = 0.1):
        super().__init__("dropout")
        assert 0<=p<=1, "p 是dropout 概率，必须在[0, 1]中"
        self.p = p
        self.dropout = True

    def cal(self, X):
        if self.dropout:
            X = X.copy()
            mask = np.random.rand(*X.shape) < self.p
            np.putmask(X, mask, 0)
            self.cache.append(mask)
        else:
            X = X*(1/(1-self.p))
        return X
    
    def backcal(self, grad):
        if self.dropout:
            grad = grad.copy()
            np.putmask(grad, self.cache[-1], 0)
            return grad
        else:
            return (1/(1-self.p)) * grad
    
    def eval(self):
        self.dropout=False

    def train(self):
        self.dropout=True

class Softmax(Node):
    # shape x: (*)
    # shape value: (*), softmax at dim 
    def __init__(self, dim=-1):
        super().__init__("softmax")
        self.dim = dim

    def cal(self, X):
        X = X - np.max(X, axis=self.dim, keepdims=True)
        expX = np.exp(X)
        ret = expX / expX.sum(axis=self.dim, keepdims=True)
        self.cache.append(ret)
        return ret

    def backcal(self, grad):
        softmaxX = self.cache[-1]
        grad_p = np.multiply(grad, softmaxX)
        return grad_p - np.multiply(grad_p.sum(axis=self.dim, keepdims=True), softmaxX)

class LogSoftmax(Node):
    # shape x: (*)
    # shape value: (*), logsoftmax at dim 
    def __init__(self, dim=-1):
        super().__init__("logsoftmax")
        self.dim = dim

    def cal(self, X):
        # TODO: YOUR CODE HERE
        X_max = np.max(X, axis=self.dim, keepdims=True)
        log_sum_exp = np.log(np.sum(np.exp(X - X_max), axis=self.dim, keepdims=True) + 1e-6)
        ret = X - X_max - log_sum_exp
        self.cache.append(ret)
        return ret

    def backcal(self, grad):
        # TODO: YOUR CODE HERE
        log_softmax_X = self.cache[-1]
        softmax_X = np.exp(log_softmax_X)
        grad_sum = np.sum(grad, axis=self.dim, keepdims=True)
        return grad - np.multiply(softmax_X, grad_sum)

class NLLLoss(Node):
    '''
    negative log-likelihood 损失函数
    '''
    # shape x: (*, d), y: (*)
    # shape value: number 
    # 输入：x: (*) 个预测，每个预测是个d维向量，代表d个类别上分别的log概率。  y：(*) 个整数类别标签
    # 输出：NLL损失
    def __init__(self, y):
        """
        初始化
        @param y: n 样本的label
        """
        super().__init__("NLLLoss")
        self.y = y

    def cal(self, X):
        y = self.y
        self.cache.append(X)
        return - np.sum(
            np.take_along_axis(X, np.expand_dims(y, axis=-1), axis=-1))

    def backcal(self, grad):
        X, y = self.cache[-1], self.y
        ret = np.zeros_like(X)
        np.put_along_axis(ret, np.expand_dims(y, axis=-1), -1, axis=-1)
        return grad * ret

class CrossEntropyLoss(Node):
    '''
    多分类交叉熵损失函数，不同于课上讲的二分类。它与NLLLoss的区别仅在于后者输入log概率，前者输入概率。
    '''
    # shape x: (*, d), y: (*)
    # shape value: number 
    # 输入：x: (*) 个预测，每个预测是个d维向量，代表d个类别上分别的概率。  y：(*) 个整数类别标签
    # 输出：交叉熵损失
    def __init__(self, y):
        """
        初始化
        @param y: n 样本的label
        """
        super().__init__("CELoss")
        self.y = y

    def cal(self, X):
        # TODO: YOUR CODE HERE
        # 提示，可以对照NLLLoss的cal
        y = self.y
        self.cache.append(X)
        return -np.sum(np.log(np.take_along_axis(X, np.expand_dims(y, axis=-1), axis=-1) + 1e-6))

    def backcal(self, grad):
        # TODO: YOUR CODE HERE
        # 提示，可以对照NLLLoss的backcal
        X, y = self.cache[-1], self.y
        ret = np.zeros_like(X)
        np.put_along_axis(ret, np.expand_dims(y, axis=-1), -grad, axis=-1)
        return np.multiply(ret, 1 / (np.take_along_axis(X, np.expand_dims(y, axis=-1), axis=-1) + 1e-6))



# TODO: Design my own nodes for CNN here
def im2col(input_data, filter_h, filter_w, stride=1, pad=0):
    N, C, H, W = input_data.shape
    out_h = (H + 2 * pad - filter_h) // stride + 1
    out_w = (W + 2 * pad - filter_w) // stride + 1

    img = np.pad(input_data, [(0, 0), (0, 0), (pad, pad), (pad, pad)], 'constant')
    col = np.zeros((N, C, filter_h, filter_w, out_h, out_w))

    for y in range(filter_h):
        y_max = y + stride * out_h
        for x in range(filter_w):
            x_max = x + stride * out_w
            col[:, :, y, x, :, :] = img[:, :, y:y_max:stride, x:x_max:stride]

    col = col.transpose(0, 4, 5, 1, 2, 3).reshape(N * out_h * out_w, -1)
    return col

def col2im(col, input_shape, filter_h, filter_w, stride=1, pad=0):
    N, C, H, W = input_shape
    out_h = (H + 2 * pad - filter_h) // stride + 1
    out_w = (W + 2 * pad - filter_w) // stride + 1
    col = col.reshape(N, out_h, out_w, C, filter_h, filter_w).transpose(0, 3, 4, 5, 1, 2)

    img = np.zeros((N, C, H + 2 * pad + stride - 1, W + 2 * pad + stride - 1))
    for y in range(filter_h):
        y_max = y + stride * out_h
        for x in range(filter_w):
            x_max = x + stride * out_w
            img[:, :, y:y_max:stride, x:x_max:stride] += col[:, :, y, x, :, :]

    return img[:, :, pad:H + pad, pad:W + pad]

class Conv2D(Node):
    def __init__(self, input_channels, output_channels, kernel_size, stride=1, padding=0):
        weight = 0.01 * np.random.randn(output_channels, input_channels, kernel_size, kernel_size)
        bias = np.zeros(output_channels)
        super().__init__("Conv2D", weight, bias)
        self.stride = stride
        self.padding = padding

    def cal(self, X):
        FN, C, FH, FW = self.params[0].shape
        N, C, H, W = X.shape
        out_h = 1 + (H + 2 * self.padding - FH) // self.stride
        out_w = 1 + (W + 2 * self.padding - FW) // self.stride

        col = im2col(X, FH, FW, self.stride, self.padding)
        col_W = self.params[0].reshape(FN, -1).T
        out = np.dot(col, col_W) + self.params[1]
        out = out.reshape(N, out_h, out_w, -1).transpose(0, 3, 1, 2)

        self.cache.append((X, col, col_W))
        return out

    def backcal(self, grad):
        FN, C, FH, FW = self.params[0].shape
        X, col, col_W = self.cache[-1]
        grad = grad.transpose(0, 2, 3, 1).reshape(-1, FN)

        db = np.sum(grad, axis=0)
        dW = np.dot(col.T, grad)
        dW = dW.transpose(1, 0).reshape(FN, C, FH, FW)

        dcol = np.dot(grad, col_W.T)
        dx = col2im(dcol, X.shape, FH, FW, self.stride, self.padding)

        self.grad.append(dW)
        self.grad.append(db)

        return dx

class MaxPool2D(Node):
    def __init__(self, pool_size, stride=2, padding=0):
        super().__init__("MaxPool2D")
        self.pool_size = pool_size
        self.stride = stride
        self.padding = padding
        self.x = None
        self.arg_max = None

    def cal(self, x):
        N, C, H, W = x.shape
        out_h = (H - self.pool_size) // self.stride + 1
        out_w = (W - self.pool_size) // self.stride + 1

        col = im2col(x,self.pool_size,self.pool_size,self.stride,self.padding)
        col = col.reshape(-1,self.pool_size * self.pool_size)
        
        arg_max = np.argmax(col, axis=1)
        out = np.max(col, axis=1)
        out = out.reshape(N,out_h,out_w,C).transpose(0,3,1,2)

        self.x = x
        self.arg_max = arg_max
        
        return out

    def backcal(self, grad):
        grad = grad.transpose(0, 2, 3, 1)
        pool_size = self.pool_size ** 2
        
        dmax = np.zeros((grad.size, pool_size))
        dmax[np.arange(self.arg_max.size), self.arg_max.flatten()] = grad.flatten()
        dmax = dmax.reshape(grad.shape + (pool_size,))
        
        dcol = dmax.reshape(dmax.shape[0] * dmax.shape[1] * dmax.shape[2], -1)
        dx = col2im(dcol, self.x.shape, self.pool_size, self.pool_size, self.stride, self.padding)

        return dx
    
    def flush(self):
        self.x = None
        self.arg_max = None

class Flatten(Node):
    def __init__(self):
        super().__init__("Flatten")

    def cal(self, X):
        # Flatten the input tensor
        batch_size = X.shape[0]
        output = X.reshape(batch_size, -1)
        self.cache = X.shape
        return output

    def backcal(self, grad):
        # Calculate the gradient
        original_shape = self.cache
        dX = grad.reshape(original_shape)
        return dX

class MyBatchNorm(Node):
    '''
    input shape (*)
    output shape (*)
    '''
    EPS = 1e-3
    def __init__(self, indim, momentum: float = 0.9):
        super().__init__("mybatchnorm", np.ones((indim)), np.zeros(indim))
        self.momentum = momentum
        self.mean = None
        self.std = None
        self.updatemean = True
        self.indim = indim

    def cal(self, X):
        n, c, h, w = X.shape
        X = X.reshape(n, c, -1)  # Reshape to (n, c, h*w)
        
        if self.updatemean:
            tmean, tstd = np.mean(X, axis=(0, 2), keepdims=True), np.std(X, axis=(0, 2), keepdims=True)
            if self.std is None or self.std is None:
                self.mean = tmean
                self.std = tstd
            else:
                self.mean *= self.momentum
                self.mean += (1-self.momentum) * tmean
                self.std *= self.momentum
                self.std += (1-self.momentum) * tstd
        X = X.copy()
        X -= self.mean
        X /= (self.std + self.EPS)
        self.cache.append(X.copy())
        
        gamma = self.params[0].reshape(1, c, 1)  # Reshape gamma to (1, c, 1) for proper broadcasting
        beta = self.params[1].reshape(1, c, 1)   # Reshape beta to (1, c, 1) for proper broadcasting
        
        X *= gamma
        X += beta
        
        return X.reshape(n, c, h, w)  # Reshape back to (n, c, h, w)

    def backcal(self, grad):
        n, c, h, w = grad.shape
        grad = grad.reshape(n, c, -1)  # Reshape to (n, c, h*w)
        X = self.cache[-1]

        self.grad.append(np.multiply(X, grad).sum(axis=(0, 2)))
        self.grad.append(grad.sum(axis=(0, 2)))

        gamma = self.params[0].reshape(1, c, 1)  # Reshape gamma to (1, c, 1) for proper broadcasting

        return ((grad * gamma) / (self.std + self.EPS)).reshape(n, c, h, w)  # Reshape back to (n, c, h, w)

    def eval(self):
        self.updatemean = False

    def train(self):
        self.updatemean = True
