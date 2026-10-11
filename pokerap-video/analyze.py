import sys, subprocess, numpy as np
f=sys.argv[1]; W,H=180,320
p=subprocess.run(["ffmpeg","-v","error","-i",f,"-vf",f"scale={W}:{H}","-f","rawvideo","-pix_fmt","rgb24","-"],capture_output=True)
a=np.frombuffer(p.stdout,np.uint8).reshape(-1,H,W,3).astype(int)
out=[]
for i,fr in enumerate(a):
    c=fr[90:260,30:150]
    dark=((c.sum(-1))<120).mean()
    top=fr[20:70,20:160]
    yel=((top[...,0]>200)&(top[...,1]>170)&(top[...,2]<90)).mean()
    # grid: lots of small cells -> check mid grey/white grid lines region
    g=fr[100:280,20:160]
    out.append((i/30,dark,yel))
    print(f"{i/30:.3f} {dark:.3f} {yel:.3f}")
