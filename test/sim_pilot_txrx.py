import numpy as np
from qampy.core import equalisation,  phaserecovery, pilotbased_receiver,pilotbased_transmitter,filter,\
    resample,impairments
from qampy import signals
import matplotlib.pylab as plt
import copy
from scipy import signal

def run_pilot_receiver(rec_signal, process_frame_id=0, sh=False, os=2, M=128, Numtaps=(17, 45),
                       frame_length=2 ** 16, method=('cma', 'cma'), pilot_seq_len=512, pilot_ins_ratio=32,
                       Niter=(10, 30), mu=(1e-3, 1e-3), adap_step=(True, True), cpe_average=5, use_cpe_pilot_ratio=1,
                       remove_inital_cpe_output=True, remove_phase_pilots=True):

    #rec_signal = np.atleast_2d(rec_signal)
    tap_cor = int((Numtaps[1] - Numtaps[0]) / 2)
    #npols = rec_signal.shape[0]
    # Extract pilot sequence
    #ref_symbs = (pilot_symbs[:, :pilot_seq_len])
    ref_symbs = rec_signal.pilot_seq

    # Frame sync, locate first frame
    shift_factor, corse_foe, mode_alignment = pilotbased_receiver.frame_sync(rec_signal, ref_symbs, os, frame_length=frame_length,
                                                              mu=mu[0], method=method[0], ntaps=Numtaps[0],
                                                              Niter=Niter[0], adap_step=adap_step[0])

    #shift_factor = [0,0]
    # Redistribute pilots according to found modes
    #pilot_symbs = rec_signal.pilots
    pilot_symbs = rec_signal.pilots[mode_alignment,:]
    ref_symbs = ref_symbs[mode_alignment,:]
    # taps cause offset on shift factors
    shift_factor = pilotbased_receiver.correct_shifts(shift_factor, Numtaps, os)
    # shift so that other modes are offset from minimum mode
    rec_signal = np.roll(rec_signal, -shift_factor.min(), axis=-1)
    shift_factor -= shift_factor.min()

    
    # Converge equalizer using the pilot sequence
    taps, foePerMode = pilotbased_receiver.equalize_pilot_sequence(rec_signal, ref_symbs,
                                                                    os, sh=sh, process_frame_id=process_frame_id,
                                                                    frame_length=frame_length,
                                                                    mu=mu, method=method,
                                                                    ntaps=Numtaps, Niter=Niter,
                                                                    adap_step=adap_step)




    # DSP for the payload: Equalization, FOE, CPE. All pilot-aided
    dsp_sig_out = []
    phase_trace = []
    #sig_out = apply_filter
    if not sh:
        out_sig = phaserecovery.comp_freq_offset(rec_signal, foePerMode, os=os)
    else:
        out_sig = rec_signal
    eq_mode_sig = equalisation.apply_filter(out_sig, os, taps, method="pyx")
    eq_mode_sig = pilotbased_receiver.shift_signal(eq_mode_sig, shift_factor)
    symbs, trace = pilotbased_receiver.pilot_based_cpe(eq_mode_sig[:, pilot_seq_len:frame_length],
                                                           pilot_symbs[:, pilot_seq_len:], pilot_ins_ratio,
                                                           use_pilot_ratio=use_cpe_pilot_ratio, num_average=cpe_average,
                                                       remove_phase_pilots=True)


    return symbs, trace, eq_mode_sig


def pre_filter(signal, bw, os,center_freq = 0):
    """
    Low-pass pre-filter signal with square shape filter

    Parameters
    ----------

    signal : array_like
        single polarization signal

    bw     : float
        bandwidth of the rejected part, given as fraction of overall length
    """
    N = len(signal)
    freq_axis = np.fft.fftfreq(N, 1 / os)

    idx = np.where(abs(freq_axis-center_freq) < bw / 2)

    h = np.zeros(N, dtype=np.float64)
    # h[int(N/(bw/2)):-int(N/(bw/2))] = 1
    h[idx] = 1
    s = np.fft.ifftshift(np.fft.ifft(np.fft.fft(signal) * h))
    return s

# Standard function to test DSP
def sim_pilot_txrx(sig_snr, Ntaps=45, beta=0.1, M=256, freq_off = None,cpe_avg=2,
                   frame_length = 2**14, pilot_seq_len = 8192, pilot_ins_rat=32,
                   num_frames=3,modal_delay=None, laser_lw = None,
                   resBits_tx=None, resBits_rx=None):
    
    npols=2
    
    signal = signals.SignalWithPilots(M, frame_length, pilot_seq_len, pilot_ins_rat, nframes=num_frames, nmodes=npols)

    signal2 = signal.resample(signal.fb*2, beta=beta, renormalise=True)
    # Simulate transmission
    sig_tx = pilotbased_transmitter.sim_tx(signal2, 2, snr=sig_snr, modal_delay=[100, 200], freqoff=freq_off,
                                                    linewidth=laser_lw,beta=beta, num_frames=3, resBits_tx=resBits_tx,
                                                    resBits_rx=resBits_rx)
    sig_tx = signal2.recreate_from_np_array(sig_tx)



    # Run DSP
    dsp_out, phase, dsp_out2 = run_pilot_receiver(sig_tx,
                                 frame_length=sig_tx.frame_len, M=M, pilot_seq_len=sig_tx.pilot_seq.shape[-1],
                                 pilot_ins_ratio=sig_tx._pilot_ins_rat,cpe_average=cpe_avg,os=int(sig_tx.fs/sig_tx.fb) ,
                                 Numtaps=(17,Ntaps), mu = (1e-3, 1e-3), method=("cma","sbd"))

    # Calculate GMI and BER
    #ber_res = np.zeros(npols)
    #sout = signal.recreate_from_np_array(np.array(dsp_out[1]))
    #for l in range(npols):
        #gmi_res[l] = signal.cal_gmi(dsp_out[1][:])[0][0]
        #ber_res[l] = signal.cal_ber(np.vstackdsp_out[1][l])
    #gmi_res = sout.cal_gmi()[0]
    #ber_res = sout.cal_ber()

        
    return dsp_out, sig_tx, phase, signal, dsp_out2
    #return dsp_out, signal

if __name__ == "__main__":
    #gmi, ber = sim_pilot_txrx(20)
    dsp, sig, ph, sign, sig2 = sim_pilot_txrx(40)
    sigo = sign.symbols.recreate_from_np_array(dsp)
    print(sigo.cal_gmi())
