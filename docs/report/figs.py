"""Redraw the report figures from the result summaries (no simulation).
Run from the repository root:  python3 docs/report/figs.py
Needs results/ (gitignored, on the analysis machine), numpy and matplotlib."""
import csv, os, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyArrowPatch
HERE=os.path.dirname(os.path.abspath(__file__))
ROOT=os.path.abspath(os.path.join(HERE,"..",".."))
OUT=os.path.join(HERE,"fig")+os.sep
os.makedirs(OUT,exist_ok=True)
BLUE,ORANGE,AQUA,VIOLET="#2a78d6","#eb6834","#1baf7a","#6250d6"
INK,INK2,GRID="#1b1b1a","#52514e","#e4e3df"
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9.5,"axes.edgecolor":INK2,"axes.labelcolor":INK,
 "xtick.color":INK2,"ytick.color":INK2,"axes.spines.top":False,"axes.spines.right":False,"axes.grid":True,
 "grid.color":GRID,"grid.linewidth":0.6,"lines.linewidth":2,"legend.frameon":False,"savefig.dpi":220,"axes.titlesize":10,"axes.titleweight":"bold","axes.axisbelow":True})
from matplotlib.ticker import FuncFormatter, LogLocator
PL=FuncFormatter(lambda v,p: f"{v:g}")
def save(f,n): f.savefig(OUT+n,bbox_inches="tight"); plt.close(f)

# ---------- data
cu=list(csv.DictReader(open(os.path.join(ROOT,"results/copper_baseline_gasgap/summary_cu90.csv"))))
cu=[r for r in cu if r["set"]=="Cu90_dV1900"]
gl=list(csv.DictReader(open(os.path.join(ROOT,"results/glass_signal/quicktest_gasgap/summary_cu90.csv"))))
nom=np.array([0.1,0.2,0.5,1.0]); gas=nom-0.09
def arm(a,key): return np.array([float(r[key]) for r in gl if r["arm"]==a])
def lab(name):
    rows=list(csv.DictReader(open(os.path.join(HERE,"lab_data",name+".csv"))))
    out={}
    for e in ("1.5","2.0","2.5"):
        rr=[r for r in rows if r["E_ind_kV_cm"]==e]
        out[e]={k:np.array([float(r[k]) for r in rr]) for k in ("gap_nominal_mm","value","errbar_halfwidth","box_halfwidth")}
    return out
LR,LT,LA=lab("charge_ratio"),lab("top_charge"),lab("anode_charge")
labR=LR["1.5"]["value"][:4]; labRbox=LR["1.5"]["box_halfwidth"][:4]
labT=LT["1.5"]["value"][:4]; labTbox=LT["1.5"]["box_halfwidth"][:4]
labA=LA["1.5"]["value"][:4]; labAbox=LA["1.5"]["box_halfwidth"][:4]
SER=[("1.5",BLUE,"o"),("2.0",ORANGE,"s"),("2.5",AQUA,"^")]
def labplot(ax,D,e,c,m,label,dx=1.0,ms=5,lw=1.5,ls="-"):
    x=D[e]["gap_nominal_mm"]*dx; y=D[e]["value"]; bw=D[e]["box_halfwidth"]; eb=D[e]["errbar_halfwidth"]
    for xi,yi,bi in zip(x,y,bw): ax.add_patch(Rectangle((xi*0.955,yi-bi),xi*0.09,2*bi,fc=c,alpha=0.18,lw=0))
    ax.errorbar(x,y,yerr=eb,fmt=m+ls,color=c,ms=ms,lw=lw,capsize=2,label=label)

# ---------- Fig 1 geometry schematic (one hole, cross-section)
f,ax=plt.subplots(figsize=(7.2,4.6)); ax.set_axis_off(); ax.grid(False)
W=2.0  # x from -1 to 1 mm (one pitch centred on a hole), scale 1:1 in mm except drift gap broken
cuT=0.09; fr4=0.8; gap=0.41; glass=0.8
y_bot=0; # bottom-Cu lower face at y=0
y_glass_top=-gap; y_pad=-gap-glass
def slab(y0,h,col,hole=True,lab=None):
    if hole:
        for xs in [(-1,-0.25),(0.25,1)]: ax.add_patch(Rectangle((xs[0],y0),xs[1]-xs[0],h,fc=col,ec="none"))
    else: ax.add_patch(Rectangle((-1,y0),2,h,fc=col,ec="none"))
CU="#c27c3a"; FR="#9cb98a"; GL="#bcd6ea"
# copper with 100um rim: copper hole radius 0.35, FR4 hole radius 0.25
for xs in [(-1,-0.35),(0.35,1)]:
    ax.add_patch(Rectangle((xs[0],0),xs[1]-xs[0],cuT,fc=CU))
    ax.add_patch(Rectangle((xs[0],cuT+fr4),xs[1]-xs[0],cuT,fc=CU))
for xs in [(-1,-0.25),(0.25,1)]: ax.add_patch(Rectangle((xs[0],cuT),xs[1]-xs[0],fr4,fc=FR))
ax.add_patch(Rectangle((-1,y_pad),2,glass,fc=GL)); ax.add_patch(Rectangle((-1,y_pad-0.07),2,0.07,fc=CU))
yc=cuT*2+fr4+0.55; ax.plot([-1,1],[yc,yc],color=INK2,lw=2.5)
ax.text(1.05,yc,"drift cathode (5 mm above; drawn shortened)",va="center",fontsize=8.5,color=INK)
ax.text(1.05,cuT+fr4+cuT/2,"THGEM top Cu (90 µm), read out\nΔV = 1.9 kV across the plate",va="center",fontsize=8.5)
ax.text(1.05,cuT+fr4/2,"FR4 0.8 mm, hole Ø 0.5 mm,\nrim 0.1 mm, pitch 1.0 mm (hex)",va="center",fontsize=8.5)
ax.text(1.05,cuT/2,"THGEM bottom Cu (90 µm), grounded",va="center",fontsize=8.5)
ax.text(1.05,-gap/2,"induction gap (gas)",va="center",fontsize=8.5)
ax.text(1.05,y_pad+glass/2,"resistive glass 0.8 mm\nρ = 1e10 Ω·cm, ε_r ≈ 6–8 (assumed)",va="center",fontsize=8.5)
ax.text(1.05,y_pad-0.035,"anode pad 2×2 cm, read out",va="center",fontsize=8.5)
# gap dims
ax.annotate("",xy=(-1.12,cuT),xytext=(-1.12,-gap),arrowprops=dict(arrowstyle="<->",color=INK,lw=1))
ax.text(-1.17,(cuT-gap)/2,"nominal d\n(spacer:\nFR4 → glass)",ha="right",va="center",fontsize=8.5)
ax.annotate("",xy=(-0.75,0),xytext=(-0.75,-gap),arrowprops=dict(arrowstyle="<->",color=BLUE,lw=1))
ax.text(-0.7,-gap/2,"gas gap\n= d − 90 µm",va="center",fontsize=8.5,color=BLUE)
# electron path
ax.annotate("",xy=(0.05,-gap+0.01),xytext=(0.0,yc-0.05),arrowprops=dict(arrowstyle="->",color=ORANGE,lw=1.4,linestyle="--"))
ax.text(0.08,cuT+fr4+0.3,"e⁻ drift (1 kV/cm)",fontsize=8,color=ORANGE)
ax.annotate("avalanche in the hole\n(tens of kV/cm)",xy=(0.0,cuT+0.4),xytext=(-1.85,cuT+fr4+0.3),fontsize=8,color=ORANGE,arrowprops=dict(arrowstyle="->",color=ORANGE,lw=0.8))
ax.text(0.12,-gap/2,"e⁻ to glass",fontsize=8,color=ORANGE,va="center")
ax.set_xlim(-1.9,3.4); ax.set_ylim(y_pad-0.15,yc+0.25); ax.set_aspect("equal")
ax.text(-1.9,yc+0.17,"one hole, cross-section, to scale (drawn for d = 0.5 mm)",fontsize=8.5,color=INK2)
save(f,"fig_geometry.png")

# ---------- Fig 2 weighting potential planar: copper vs glass
f,axs=plt.subplots(1,2,figsize=(7.4,3.0))
g=0.41; b=0.8; er=7
z=np.linspace(-b,g,400)
phiCu=np.where(z>=0,1-z/g,np.nan)
f_=g/(g+b/er)
Eg=1/(g+b/er)
phiGl=np.where(z>=0,f_*(1-z/g), f_+ (1-f_)*(-z/b))
ax=axs[0]
ax.plot(phiCu,z,color=INK2,label="metal anode at the gas boundary")
ax.plot(phiGl,z,color=BLUE,label=f"pad behind glass (ε_r = {er})")
ax.axhspan(-b,0,color=GL,alpha=0.5,lw=0); ax.axhline(g,color=CU,lw=3); 
ax.text(0.05,-0.3,"glass",fontsize=8.5); ax.text(0.02,g/2,"gas gap",fontsize=8.5)
ax.annotate(f"f = {f_:.2f}",xy=(f_,0),xytext=(f_+0.1,0.12),arrowprops=dict(arrowstyle="->",color=INK2),fontsize=8.5)
ax.set_xlabel("anode weighting potential φ_w")
ax.set_yticks([-0.8,-0.4,0,0.41]); ax.set_yticklabels(["pad","","glass top","bottom Cu"])
ax.set_title("Weighting potential (planar, g = 0.41 mm)"); ax.legend(fontsize=7,loc="lower left")
ax=axs[1]
gg=np.logspace(-2.2,0.4,200)
for e,c in [(4,ORANGE),(8,BLUE),(12,AQUA)]:
    ax.plot(gg,gg/(gg+b/e),color=c,label=f"ε_r = {e}")
ax.set_xscale("log"); ax.set_xlabel("gas gap g [mm]"); ax.set_ylabel("f = g / (g + b/ε_r)")
ax.set_title("Planar glass factor, b = 0.8 mm"); ax.legend(fontsize=8); ax.set_ylim(0,1)
f.tight_layout(); save(f,"fig_weighting.png")

# ---------- Fig 3 signal timeline schematic
f,ax=plt.subplots(figsize=(7.0,2.6))
t=np.linspace(-2,300,2000)
Qe=np.where(t>0,1-np.exp(-np.clip(t,0,None)/0.05),0)*0.45
Qi=np.where(t>0,0.55*(1-np.exp(-np.clip(t,0,None)/3.0)),0)
Q=(Qe+Qi)*np.exp(-np.clip(t,0,None)/100)
ax.plot(t,Q,color=BLUE,label="CSA output (schematic)")
ax.plot(t,(Qe+Qi),color=INK2,lw=1,ls="--",label="ideal integrator (no decay)")
ax.axvline(10,color=ORANGE,lw=1); ax.text(12,0.15,"simulation scores the\ncharge inventory at 10 µs",fontsize=8,color=ORANGE)
ax.set_xlabel("time after the X-ray [µs]"); ax.set_ylabel("charge [arb.]"); ax.set_xlim(-5,300)
ax.text(120,0.75,"decay constant 100 µs",fontsize=8,color=INK2)
ax.set_title("What the preamplifier sees (illustration, not data)"); ax.legend(fontsize=8,loc="lower right")
save(f,"fig_timeline.png")

# ---------- Fig 4 measured data
f,axs=plt.subplots(1,3,figsize=(7.6,2.9))
ticks=([0.1,0.2,0.5,1,2],["0.1","0.2","0.5","1","2"])
for ax,D,t,yl in [(axs[0],LR,"Ratio R","Q_anode / Q_top"),(axs[1],LT,"Top charge","charge per event [pC]"),(axs[2],LA,"Anode charge","charge per event [pC]")]:
    for (e,c,m),dx in zip(SER,(0.97,1.0,1.03)):
        labplot(ax,D,e,c,m,f"E_ind {e}",dx=dx)
    ax.set_xscale("log"); ax.set_xticks(*ticks); ax.set_xticks([],minor=True); ax.set_title(t); ax.set_ylabel(yl); ax.set_xlabel("nominal gap d [mm]")
axs[0].set_ylim(0.4,1.0); axs[0].legend(fontsize=7,title="kV/cm",title_fontsize=7)
f.tight_layout(); save(f,"fig_measured.png")

# ---------- Fig 5 copper baseline with loss bars
f,axs=plt.subplots(1,2,figsize=(7.4,3.0),gridspec_kw=dict(width_ratios=[1,1.15]))
an=np.array([float(r["anode_excl_att"]) for r in cu]); lo=np.array([float(r["lo"]) for r in cu]); hi=np.array([float(r["hi"]) for r in cu])
ax=axs[0]
ax.errorbar(nom,an,yerr=[an-lo,hi-an],fmt="o-",color=BLUE,ms=6,capsize=3,label="sim, copper anode")
ax.set_xscale("log"); ax.set_xticks(nom); ax.set_xticklabels(["0.1","0.2","0.5","1.0"]); ax.set_ylim(0.4,1.02)
ax.set_xlabel("nominal gap d [mm]"); ax.set_ylabel("anode e⁻ fraction"); ax.set_title("Copper-anode electron fraction")
for x,y in zip(nom,an): ax.annotate(f"{y:.2f}",(x,y),textcoords="offset points",xytext=(5,5),fontsize=8,color=INK2)
ax=axs[1]
keys=[("loss_bottom Cu underside","bottom-Cu underside",ORANGE),("loss_hole wall, lowest 100 um","FR4 wall, lowest 100 µm",AQUA),("loss_hole wall, lower half (above)","FR4 wall above",VIOLET)]
xs=np.arange(4); bottom=np.zeros(4)
for k,l,c in keys:
    v=np.array([float(r[k] or 0) for r in cu]); ax.bar(xs,v,0.6,bottom=bottom,color=c,label=l,edgecolor="white",linewidth=1); bottom+=v
ax.set_xticks(xs); ax.set_xticklabels(["0.1","0.2","0.5","1.0"]); ax.set_xlabel("nominal gap d [mm]")
ax.set_ylabel("fraction of avalanche e⁻ lost"); ax.set_title("Where the lost electrons end"); ax.legend(fontsize=7.5,loc="upper left")
f.tight_layout(); save(f,"fig_copper.png")

# ---------- Fig 6 R comparison
f,axs=plt.subplots(1,2,figsize=(7.4,3.1))
ax=axs[0]
Rcu=arm("Cu","R"); Rcl=arm("Cu","R_lo"); Rch=arm("Cu","R_hi")
ax.errorbar(nom,Rcu,yerr=[Rcu-Rcl,Rch-Rcu],fmt="s-",color=INK2,ms=5,capsize=3,lw=1.5,label="sim R_Cu (copper anode)")
R4=arm("4.0","R");R12=arm("12.0","R");R6=arm("6.0","R");R8=arm("8.0","R")
ax.fill_between(nom,R4,R12,color=BLUE,alpha=0.15,lw=0,label="sim R_glass, ε_r 4–12")
ax.fill_between(nom,R6,R8,color=BLUE,alpha=0.45,lw=0,label="sim R_glass, ε_r 6–8")
labplot(ax,LR,"1.5",ORANGE,"o","lab R (E_ind 1.5)",ms=6,lw=2)
ax.set_xscale("log"); ax.set_xticks([0.1,0.2,0.5,1,2]); ax.set_xticklabels(["0.1","0.2","0.5","1","2"]); ax.set_xticks([],minor=True); ax.set_ylim(0,1.15)
ax.set_xlabel("nominal gap d [mm]"); ax.set_ylabel("R = Q_anode / Q_top"); ax.set_title("Ratio: simulation vs lab"); ax.legend(fontsize=7.2,loc="lower right")
ax=axs[1]
F6=arm("6.0","F");F8=arm("8.0","F")
ax.fill_between(nom,F6,F8,color=BLUE,alpha=0.45,lw=0,label="sim F (3D), ε_r 6–8")
for e,ls in [(6,":"),(8,"--")]:
    ax.plot(nom,gas/(gas+0.8/e),ls,color=BLUE,lw=1.3,label=f"planar f(gas gap), ε_r {e}")
Fn=labR/Rcu; Fnl=(labR-labRbox)/Rch; Fnh=(labR+labRbox)/Rcl
ax.fill_between(nom,Fnl,Fnh,color=ORANGE,alpha=0.18,lw=0)
ax.plot(nom,Fn,"o-",color=ORANGE,ms=6,label="F the data need = lab R / sim R_Cu")
ax.axhline(1,color=INK2,lw=1)
ax.set_xscale("log"); ax.set_xticks([0.1,0.2,0.5,1,2]); ax.set_xticklabels(["0.1","0.2","0.5","1","2"]); ax.set_xticks([],minor=True); ax.set_ylim(0,1.3)
ax.set_xlim(0.085,1.2); ax.set_xlabel("nominal gap d [mm]"); ax.set_ylabel("glass factor F = R_glass / R_Cu"); ax.set_title("Glass factor"); ax.legend(fontsize=7.2,loc="lower right")
f.tight_layout(); save(f,"fig_ratio.png")

# ---------- Fig 7 charges
f,axs=plt.subplots(1,2,figsize=(7.4,3.0))
ax=axs[0]
T=arm("6.0","top_pC");Tl=arm("6.0","top_lo");Th=arm("6.0","top_hi")
ax.errorbar(nom,T,yerr=[T-Tl,Th-T],fmt="s-",color=BLUE,ms=5,capsize=3,label="sim Q_top (glass ε_r 6)")
labplot(ax,LT,"1.5",ORANGE,"o","lab Q_top (E_ind 1.5)",ms=6,lw=2)
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xticks([0.1,0.2,0.5,1,2]); ax.set_xticklabels(["0.1","0.2","0.5","1","2"]); ax.set_xticks([],minor=True)
ax.yaxis.set_major_formatter(PL); ax.yaxis.set_minor_formatter(FuncFormatter(lambda v,p: f"{v:g}" if round(v*10) in (2,3,5) or round(v) in (2,3) else "")); ax.set_xlabel("nominal gap d [mm]"); ax.set_ylabel("charge per event [pC]"); ax.set_title("Top-electrode charge"); ax.legend(fontsize=7.5)
for x,a,bb in zip(nom,T,labT): ax.annotate(f"×{a/bb:.1f}",(x,a),textcoords="offset points",xytext=(4,6),fontsize=8,color=INK2)
ax=axs[1]
A6=-arm("6.0","anode_pC"); B6=-arm("6.0","bottom_pC"); Acu=-arm("Cu","anode_pC"); Bcu=-arm("Cu","bottom_pC")
ax.plot(nom,Acu,"s-",color=INK2,ms=5,lw=1.5,label="anode, copper")
ax.plot(nom,A6,"s-",color=BLUE,ms=5,label="anode, glass ε_r 6")
ax.plot(nom,B6,"^--",color=AQUA,ms=6,label="|bottom|, glass ε_r 6")
ax.plot(nom,np.abs(Bcu),"^:",color=INK2,ms=5,lw=1.2,label="|bottom|, copper")
labplot(ax,LA,"1.5",ORANGE,"o","lab anode (E_ind 1.5)",ms=6,lw=2)
ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xticks([0.1,0.2,0.5,1,2]); ax.set_xticklabels(["0.1","0.2","0.5","1","2"]); ax.set_xticks([],minor=True)
ax.yaxis.set_major_formatter(PL); ax.set_xlabel("nominal gap d [mm]"); ax.set_ylabel("|charge| per event [pC]"); ax.set_title("Anode and bottom charges (sim)"); ax.legend(fontsize=7)
f.tight_layout(); save(f,"fig_charges.png")

# ---------- Fig 9 copper baseline implied by the lab
f,ax=plt.subplots(figsize=(4.6,3.0))
ax.errorbar(nom,Rcu,yerr=[Rcu-Rcl,Rch-Rcu],fmt="s-",color=INK2,ms=5,capsize=3,lw=1.5,label="sim R_Cu")
lo=(labR-labRbox)/F8; hi=(labR+labRbox)/F6
ax.fill_between(nom,lo,hi,color=ORANGE,alpha=0.25,lw=0,label="lab R / sim F (ε_r 6–8, box width)")
ax.plot(nom,labR/((F6+F8)/2),"o-",color=ORANGE,ms=6,label="lab R / sim F (ε_r 7)")
for x,a,b in zip(nom[1:],(labR/((F6+F8)/2))[1:],Rcu[1:]): ax.annotate(f"×{a/b:.2f}",(x,a),textcoords="offset points",xytext=(5,5),fontsize=8,color=INK2)
ax.set_xscale("log"); ax.set_xticks(nom); ax.set_xticklabels(["0.1","0.2","0.5","1.0"]); ax.set_xticks([],minor=True)
ax.set_xlabel("nominal gap d [mm]"); ax.set_ylabel("copper-anode ratio R_Cu"); ax.set_title("Copper baseline: simulated vs implied by the lab"); ax.legend(fontsize=7)
save(f,"fig_implied.png")
#print("implied", labR/F6, labR/F8, "sim", Rcu, "ratio", labR/((F6+F8)/2)/Rcu, "Fneed", Fn, Fnl, Fnh)
