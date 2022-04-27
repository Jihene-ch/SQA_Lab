import soxr
import torch
import argparse
import audiofile as af

from scipy.special import softmax
from python_speech_features import logfbank


mdl_bad_kwargs = {
    "channels": 16, 
    "block": "BasicBlock", 
    "num_blocks": [2,2,2,2], 
    "embd_dim": 1024, 
    "drop": 0.3, 
    "n_class": 2
}

logfbank_kwargs = {
    "winlen": 0.025, 
    "winstep": 0.01, 
    "nfilt": 80, 
    "nfft": 2048, 
    "lowfreq": 50, 
    "highfreq": None, 
    "preemph": 0.97    
}


# parse args
def parse_args():
    desc="infer labels"
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument("--data", type=str, required=True)
    parser.add_argument('--model-bad', type=str, required=True)
    parser.add_argument('--device', type=str, default="cpu")
    parser.add_argument('--nt', type=float, default=0.5, help="noise threshold, default: 0.5")
    return parser.parse_args()

def extract_feat(wav_path, samplerate=16000, cmn=True):
    kwargs = {
        "winlen": 0.025,
        "winstep": 0.01,
        "nfilt": 80,
        "nfft": 2048,
        "lowfreq": 50,
        "highfreq": 8000,
        "preemph": 0.97
    }
    y, sr = af.read(wav_path)
    if sr!=samplerate:
        y = soxr.resample(x, sr, samplerate)
        sr = samplerate
    logfbankFeat = logfbank(y, sr, **kwargs)
    if cmn:
        logfbankFeat -= logfbankFeat.mean(axis=0, keepdims=True)
    return logfbankFeat.astype('float32')
    

class SVExtractor():
    def __init__(self, mdl_kwargs, model_path, device):
        self.model = self.load_model(mdl_kwargs, model_path, device)
        self.model.eval()
        self.device = device
        self.model = self.model.to(self.device)

    @staticmethod
    def load_model(mdl_kwargs, model_path, device):
        model = torch.load(model_path, map_location=device)
        return model

    def __call__(self, frame_feats):
        feat = torch.from_numpy(frame_feats).unsqueeze(0)
        feat = feat.float().to(self.device)
        with torch.no_grad():
            embd = self.model(feat)
        embd = embd.squeeze(0).cpu().numpy()
        return embd
    
def infer_bad(wav, detector, noise_thres, int2label_dict):
    wav_feats = extract_feat(wav)
    logits = softmax(detector(wav_feats))
    hasBird = (logits[1].item() >= noise_thres)
    return hasBird, logits[1]
    
if __name__ == "__main__":

    args = parse_args()
    model_bad_path = args.model_bad
    
    int2label = {0:"0",1:"1"}
        
    print('... loading activity detector ...')
    bad_extractor = SVExtractor(mdl_bad_kwargs, model_bad_path, device=args.device)
    print('... loaded ...')
        
    pred_dict = {}
    
    wav_ = args.data
    hasBird, confidence = infer_bad(wav_, bad_extractor, args.nt, int2label)

    result = ["noise","bird"]
    print(result[hasBird],confidence)