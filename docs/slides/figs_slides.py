"""Redraw the lab-vs-sim slide figures with the exact lab data (2026-11-22).
Lab: lab_data/*.csv (values, fit-error bars, distribution-width boxes) per E_ind series.
Sim: glass quick test summary_cu90.csv (E_ind 1.5, gas gap = nominal - 90 um).
Sims are compared with the E_ind 1.5 lab series only."""
import csv, sys, os, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter
D=sys.argv[1] if len(sys.argv)>1 else "data"; OUT=sys.argv[2] if len(sys.argv)>2 else "fig"
BLUE,ORANGE,AQUA,VIOLET="#2a78d6","#eb6834","#1baf7a","#6250d6"
INK,INK2,GRID="#1b1b1a","#52514e","#e4e3df"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9.5,"axes.edgecolor":INK2,"axes.labelcolor":INK,
 "xtick.color":INK2,"ytick.color":INK2,"axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,
 "grid.color":GRID,"grid.linewidth":0.6,"lines.linewidth":2,"legend.frameon":False,"savefig.dpi":220,
 "axes.titlesize":10,"axes.titleweight":"bold","axes.axisbelow":True})
PL=FuncFormatter(lambda v,p: f"{v:g}")
def save(f,n): f.savefig(os.path.join(OUT,n),bbox_inches="tight"); plt.close(f)
def lab(name):
    out={}
    for r in csv.DictReader(open(os.path.join(D,name))):
        e=float(r["E_ind_kV_cm"]); out.setdefault(e,[]).append([float(r[k]) for k in
          ("gap_nominal_mm","value","errbar_halfwidth","box_halfwidth")])
    return {e:np.array(v) for e,v in out.items()}
R,T,A=lab("charge_ratio.csv"),lab("top_charge.csv"),lab("anode_charge.csv")
gl=list(csv.DictReader(open(os.path.join(D,"sim_glass_summary_cu90.csv"))))
def arm(a,k): return np.array([float(r[k]) for r in gl if r["arm"]==a])
nom=np.array([0.1,0.2,0.5,1.0]); gas=nom-0.09
SER=[(1.5,BLUE,"o","-"),(2.0,ORANGE,"s","-."),(2.5,AQUA,"^","--")]
def labplot(ax,arr,c,m,ls,label,boxes=True,n=None,lw=1.5):
    a=arr if n is None else arr[:n]
    if boxes:
        for x,v,eb,bw in a:
            ax.add_patch(Rectangle((x/1.09,v-bw),x*1.09-x/1.09,2*bw,fc=c,alpha=0.18,lw=0))
    ax.errorbar(a[:,0],a[:,1],yerr=a[:,2],fmt=m+ls,color=c,ms=5,lw=lw,capsize=2,label=label)
def xlog(ax,ticks):
    ax.set_xscale("log"); ax.set_xticks(ticks); ax.set_xticklabels([f"{t:g}" for t in ticks]); ax.minorticks_off()

# --- measured data: R, top, anode for the three fields
f,axs=plt.subplots(1,3,figsize=(10.2,3.0))
for (e,c,m,ls) in SER:
    labplot(axs[0],R[e],c,m,ls,f"E_ind {e:g} kV/cm")
    labplot(axs[1],T[e],c,m,ls,f"{e:g}")
    labplot(axs[2],A[e],c,m,ls,f"{e:g}")
for ax,t,yl in zip(axs,["Measured ratio R","Measured top charge","Measured anode charge"],
                   ["R = Q_anode / Q_top","Q_top per event [pC]","Q_anode per event [pC]"]):
    xlog(ax,[0.1,0.2,0.5,1,2]); ax.set_xlabel("nominal gap d [mm]"); ax.set_ylabel(yl); ax.set_title(t)
axs[0].set_ylim(0.4,1.0); axs[0].legend(fontsize=7.5,loc="lower right")
axs[2].text(0.98,0.97,"bars: fit error\nboxes: distribution width",transform=axs[2].transAxes,ha="right",va="top",fontsize=7,color=INK2)
f.tight_layout(); save(f,"fig_measured_v2.png")

# --- ratio and glass factor (sim vs lab E_ind 1.5)
L15=R[1.5][:4]; labR=L15[:,1]
f,axs=plt.subplots(1,2,figsize=(7.4,3.1))
ax=axs[0]
Rcu=arm("Cu","R"); Rcl=arm("Cu","R_lo"); Rch=arm("Cu","R_hi")
ax.errorbar(nom,Rcu,yerr=[Rcu-Rcl,Rch-Rcu],fmt="s-",color=INK2,ms=5,capsize=3,lw=1.5,label="sim R_Cu (copper anode)")
ax.fill_between(nom,arm("4.0","R"),arm("12.0","R"),color=BLUE,alpha=0.15,lw=0,label="sim R_glass, ε_r 4–12")
ax.fill_between(nom,arm("6.0","R"),arm("8.0","R"),color=BLUE,alpha=0.45,lw=0,label="sim R_glass, ε_r 6–8")
labplot(ax,R[1.5],ORANGE,"o","-","lab R, E_ind 1.5",n=4)
xlog(ax,nom); ax.set_ylim(0,1.15)
ax.set_xlabel("nominal gap d [mm]"); ax.set_ylabel("R = Q_anode / Q_top"); ax.set_title("Ratio: simulation vs lab (E_ind 1.5)"); ax.legend(fontsize=7.2,loc="lower right")
ax=axs[1]
ax.fill_between(nom,arm("6.0","F"),arm("8.0","F"),color=BLUE,alpha=0.45,lw=0,label="sim F (3D), ε_r 6–8")
for e,ls in [(6,":"),(8,"--")]:
    ax.plot(nom,gas/(gas+0.8/e),ls,color=BLUE,lw=1.3,label=f"planar f(gas gap), ε_r {e}")
need=labR/Rcu; neederr=need*np.hypot(L15[:,2]/labR,(Rch-Rcl)/2/Rcu)
ax.errorbar(nom,need,yerr=neederr,fmt="o-",color=ORANGE,ms=6,capsize=3,label="F the data need = lab R / sim R_Cu")
ax.axhline(1,color=INK2,lw=1)
xlog(ax,nom); ax.set_ylim(0,1.3)
ax.set_xlabel("nominal gap d [mm]"); ax.set_ylabel("glass factor F = R_glass / R_Cu"); ax.set_title("Glass factor"); ax.legend(fontsize=7.2,loc="lower right")
f.tight_layout(); save(f,"fig_ratio_v2.png")

# --- absolute charges
f,axs=plt.subplots(1,2,figsize=(7.4,3.0))
ax=axs[0]
Tm=arm("6.0","top_pC");Tl=arm("6.0","top_lo");Th=arm("6.0","top_hi")
ax.errorbar(nom,Tm,yerr=[Tm-Tl,Th-Tm],fmt="s-",color=BLUE,ms=5,capsize=3,label="sim Q_top (glass ε_r 6)")
labplot(ax,T[1.5],ORANGE,"o","-","lab Q_top (E_ind 1.5)",n=4)
ax.set_yscale("log"); xlog(ax,nom); ax.yaxis.set_major_formatter(PL)
ax.set_yticks([0.2,0.3,0.5,1,2,3,5]); ax.set_ylim(0.17,6)
ax.set_xlabel("nominal gap d [mm]"); ax.set_ylabel("charge per event [pC]"); ax.set_title("Top-electrode charge"); ax.legend(fontsize=7.5)
for x,a,b in zip(nom,Tm,T[1.5][:4,1]): ax.annotate(f"×{a/b:.1f}",(x,a),textcoords="offset points",xytext=(4,6),fontsize=8,color=INK2)
ax=axs[1]
A6=-arm("6.0","anode_pC"); B6=-arm("6.0","bottom_pC"); Acu=-arm("Cu","anode_pC"); Bcu=-arm("Cu","bottom_pC")
ax.plot(nom,Acu,"s-",color=INK2,ms=5,lw=1.5,label="anode, copper (sim)")
ax.plot(nom,A6,"s-",color=BLUE,ms=5,label="anode, glass ε_r 6 (sim)")
ax.plot(nom,B6,"^--",color=AQUA,ms=6,label="|bottom|, glass ε_r 6 (sim)")
ax.plot(nom,np.abs(Bcu),"^:",color=INK2,ms=5,lw=1.2,label="|bottom|, copper (sim)")
labplot(ax,A[1.5],ORANGE,"o","-","lab anode (E_ind 1.5)",n=4)
ax.set_yscale("log"); xlog(ax,nom); ax.yaxis.set_major_formatter(PL)
ax.set_yticks([0.1,0.2,0.5,1,2,5]); ax.set_ylim(0.05,6)
ax.set_xlabel("nominal gap d [mm]"); ax.set_ylabel("|charge| per event [pC]"); ax.set_title("Anode and bottom charges"); ax.legend(fontsize=6.8)
f.tight_layout(); save(f,"fig_charges_v2.png")

# --- crops of two-panel figures (left/right)
from PIL import Image
for n in ["fig_ratio_v2","fig_charges_v2"]:
    im=Image.open(os.path.join(OUT,n+".png")).convert("RGB"); a=np.asarray(im).astype(int); w=a.shape[1]
    mid=range(int(w*0.45),int(w*0.55)); x=list(mid)[int(np.argmin([(a[:,x]<245).sum() for x in mid]))]
    im.crop((0,0,x,im.size[1])).save(os.path.join(OUT,n+"_L.png")); im.crop((x,0,w,im.size[1])).save(os.path.join(OUT,n+"_R.png"))

# --- numbers for the slides
print("lab R 1.5:",labR," box:",L15[:,3])
print("Rcu:",Rcu.round(3)," F need:",need.round(3),"+-",neederr.round(3))
for e in ("4.0","6.0","8.0","12.0"): print("Rglass",e,arm(e,"R").round(3),"F",arm(e,"F").round(3))
print("Qtop sim/lab:",(Tm/T[1.5][:4,1]).round(2)," anode glass6 sim/lab:",(A6/A[1.5][:4,1]).round(2), "anode Cu sim/lab",(Acu/A[1.5][:4,1]).round(2))
print("lab R - Rglass(6..8):",(labR-arm("8.0","R")).round(3),(labR-arm("6.0","R")).round(3))
