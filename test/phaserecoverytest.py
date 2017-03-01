#import cProfile
import numpy as np
import matplotlib.pylab as plt
from dsp import equalisation, modulation, utils, phaserecovery
from timeit import default_timer as timer
import arrayfire as af



fb = 40.e9
os = 1
fs = os*fb
N = 3*10**5
M = 64
QAM = modulation.QAMModulator(M)
snr = 30
lw_LO = np.linspace(10e1, 1000e1, 2)
#lw_LO = [100e3]
sers = []


X, symbolsX, bitsX = QAM.generateSignal(N, snr, baudrate=fb, samplingrate=fs, PRBS=True)

for lw in lw_LO:
    shiftN = np.random.randint(-N/2, N/2, 1)
    xtest = np.roll(symbolsX[:(2**15-1)], shiftN)
    pp = utils.phase_noise(X.shape[0], lw, fs)
    XX = X*np.exp(1.j*pp)
    t1 = timer()
    recoverd,ph, phx= phaserecovery.blindphasesearch_af(XX, 64, QAM.symbols, 14, 16)
    ser,s,d = QAM.calculate_SER(recoverd, symbol_tx=xtest)
    t2 = timer()
    print("time  %f"%(t2-t1))
    print(ser)
    sers.append(ser)

plt.plot(lw_LO, sers)
plt.show()

