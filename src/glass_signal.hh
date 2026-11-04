// Included inside thgem_sim's anonymous namespace. All changes are opt-in.
// Snapshot charge is in units of +e; positions cm and times ns.
namespace glass_signal {
constexpr std::array<const char*, 4> labels{"anode", "thgem_top", "thgem_bottom", "drift"};
using Point = AvalancheMC::Point;
struct Track { std::vector<Point> points; int status = Garfield::StatusAlive; };
struct Growth { double end, ions, attached; };
Growth Grow(double w, double a, double e) {
  const double r = a - e;
  const double integral = w * (std::abs(r) < 1.e-8 ? 1. + r / 2. + r*r/6. : std::expm1(r)/r);
  Growth g{w * std::exp(r), integral*a, integral*e};
  if (!std::isfinite(g.end) || !std::isfinite(g.ions) || !std::isfinite(g.attached))
    throw std::runtime_error("Non-finite diagnostic avalanche weight");
  return g;
}
Point At(const std::vector<Point>& p, double t) {
  if (p.empty()) throw std::runtime_error("Empty transport path");
  if (t <= p.front().t) return p.front();
  auto it = std::lower_bound(p.begin(), p.end(), t, [](const Point& q, double v){return q.t < v;});
  if (it == p.end()) return p.back();
  const auto& b = *it; const auto& a = *(it-1);
  const double f = (t-a.t)/(b.t-a.t);
  Point q; q.x=a.x+f*(b.x-a.x); q.y=a.y+f*(b.y-a.y); q.z=a.z+f*(b.z-a.z); q.t=t;
  return q;
}
std::string Surface(const ThgemGeom& g, const Point& p, int status) {
  if (status == Garfield::StatusOutsideTimeWindow || status == Garfield::StatusAlive) return "moving";
  if (status != Garfield::StatusLeftDriftMedium && status != Garfield::StatusLeftDriftArea &&
      status != Garfield::StatusHitPlane)
    return "failed_" + std::to_string(status);
  if (p.z <= g.zAnode + 1.e-6) return "anode";
  if (p.z >= g.zDrift - 1.e-6) return "drift";
  if (status == Garfield::StatusLeftDriftArea) return "failed_lateral_escape";
  // Material identity at a boundary is ambiguous; only force conductor values
  // on planar outer faces. All other endpoints use one-sided raw potentials.
  return "surface";
}
// Partition each segment at every tessellated surface plane. Infinite planes
// only add subdivisions: medium classification selects physical intersections.
// This also catches a thin solid interval missed by midpoint-only sampling.
class CollectionBoundary {
 public:
  explicit CollectionBoundary(ThgemDetector& detector): detector_(detector), panels_(detector.BoundaryPanels()) {}
  bool Clip(Track& track) {
    const auto& g=detector_.Geom();
    for(std::size_t j=0;j+1<track.points.size();++j) {
      const Point a=track.points[j],b=track.points[j+1];
      if(std::min(a.z,b.z)>g.zTopCuTop || std::max(a.z,b.z)<g.zBotCuBot)continue;
      if(b.t<=a.t)throw std::runtime_error("Non-increasing transport times");
      const double dx=b.x-a.x,dy=b.y-a.y,dz=b.z-a.z;
      const double length=std::sqrt(dx*dx+dy*dy+dz*dz);
      std::vector<double> cuts{0.,1.};
      const int ix0=static_cast<int>(std::floor(std::min(a.x,b.x)/g.pitchCm+.5));
      const int ix1=static_cast<int>(std::floor(std::max(a.x,b.x)/g.pitchCm+.5));
      const int iy0=static_cast<int>(std::floor(std::min(a.y,b.y)/g.pitchCm+.5));
      const int iy1=static_cast<int>(std::floor(std::max(a.y,b.y)/g.pitchCm+.5));
      for(int ix=ix0;ix<=ix1;++ix)for(int iy=iy0;iy<=iy1;++iy)for(const auto& panel:panels_) {
        if(panel.xv.empty())continue;
        const double denominator=panel.a*dx+panel.b*dy+panel.c*dz;
        if(std::abs(denominator)<1.e-20)continue;
        const double f=(panel.a*(panel.xv[0]+ix*g.pitchCm-a.x)+
          panel.b*(panel.yv[0]+iy*g.pitchCm-a.y)+panel.c*(panel.zv[0]-a.z))/denominator;
        if(f>0. && f<1.)cuts.push_back(f);
      }
      std::sort(cuts.begin(),cuts.end());
      cuts.erase(std::unique(cuts.begin(),cuts.end()),cuts.end());
      for(std::size_t k=0;k+1<cuts.size();++k) {
        const double f=(cuts[k]+cuts[k+1])/2.;
        auto* medium=detector_.Component().GetMedium(a.x+f*dx,a.y+f*dy,a.z+f*dz);
        if(medium && medium->IsDriftable())continue;
        // Retain a point 1e-8 cm on the gas side, as Garfield termination does.
        const double stop=std::max(0.,cuts[k]-1.e-8/std::max(length,1.e-30));
        Point endpoint;endpoint.x=a.x+stop*dx;endpoint.y=a.y+stop*dy;
        endpoint.z=a.z+stop*dz;endpoint.t=a.t+stop*(b.t-a.t);
        track.points.resize(j+1);
        if(stop>0.)track.points.push_back(endpoint);
        if(track.points.size()<2)throw std::runtime_error("Collection at unresolved initial point");
        track.status=Garfield::StatusLeftDriftMedium;
        return true;
      }
    }
    return false;
  }
 private:
  ThgemDetector& detector_;
  std::vector<Garfield::Panel> panels_;
};
json Settings(const CliOptions& o) { return ReadJsonFile(o.configPath).value("glass_signal", json::object()); }
std::vector<double> Times(const json& d) {
  auto ts = d.value("sample_times_ns", std::vector<double>{1000.,2000.,5000.,10000.,20000.});
  if (ts.empty() || !std::is_sorted(ts.begin(), ts.end()) ||
      std::adjacent_find(ts.begin(),ts.end())!=ts.end() || ts.front() <= 0. ||
      std::any_of(ts.begin(),ts.end(),[](double t){return !std::isfinite(t);}))
    throw std::runtime_error("sample_times_ns must be finite, positive and sorted");
  return ts;
}
void Export(const CliOptions& o, Config c, const fs::path& out) {
  const auto d = Settings(o); const auto ts = Times(d);
  if (!c.simulation.mcWeightedPaths || !c.simulation.mcElectronTransport || c.fields.chargingUp)
    throw std::runtime_error("Glass export requires uncharged weighted MC transport");
  const auto K = c.simulation.mcIonSamples;
  const auto seed = static_cast<UInt_t>(c.simulation.randomSeed);
  if (!seed) throw std::runtime_error("Glass diagnostics require an explicit nonzero seed");
  gRandom->SetSeed(seed); Garfield::RandomEngineRoot rng; rng.SetSeed(seed); Garfield::Random::SetEngine(rng);
  MediumMagboltz gas(c.gas.gas1,c.gas.frac1,c.gas.gas2,100.-c.gas.frac1);
  SetupGas(gas,c.gas,true);
  ThgemDetector detector(c.geometry,c.fields,gas); if (!detector.Initialise()) throw std::runtime_error("Transport solve failed");
  const auto& g=detector.Geom(); Sensor sensor; sensor.AddComponent(&detector.Component());
  sensor.SetArea(-3*g.pitchCm,-3*g.pitchCm,g.zAnode,3*g.pitchCm,3*g.pitchCm,g.zDrift);
  CollectionBoundary boundary(detector);
  std::size_t correctedElectrons=0,correctedIons=0;
  AvalancheMC electron(&sensor), ion(&sensor);
  electron.SetDistanceSteps(c.simulation.mcStepUm*1.e-4); electron.SetTimeWindow(0.,ts.back());
  electron.EnableMultiplication(false); electron.EnableAttachment(false); electron.EnableSignalCalculation(false); electron.EnableDriftLines(true);
  ion.SetDistanceSteps(c.simulation.ionMaxStepUm*1.e-4); ion.SetTimeWindow(0.,ts.back());
  ion.EnableSignalCalculation(false); ion.EnableDriftLines(true);
  auto drift = [&](const Point& b, bool negative) {
    const bool ok = negative ? ion.DriftNegativeIon(b.x,b.y,b.z,b.t) : ion.DriftIon(b.x,b.y,b.z,b.t);
    const auto& v = negative ? ion.GetNegativeIons() : ion.GetIons();
    if (!ok || v.empty() || v.front().path.empty()) throw std::runtime_error("Diagnostic ion drift failed");
    Track tr{v.front().path,v.front().status};
    if (Surface(g,tr.points.back(),tr.status).rfind("failed_",0)==0)
      throw std::runtime_error("Unresolved original ion transport status " + std::to_string(tr.status));
    if(boundary.Clip(tr))++correctedIons;
    if (Surface(g,tr.points.back(),tr.status).rfind("failed_",0)==0)
      throw std::runtime_error("Unresolved ion transport status " + std::to_string(tr.status));
    return tr;
  };
  std::ofstream f(out/"charge_snapshots.csv.partial"); f << std::setprecision(17);
  f << "seed,path,attachment,time_ns,species,charge_e,x_cm,y_cm,z_cm,status\n";
  auto emit = [&](std::size_t path,const char* mode,double t,const char* species,double charge,const Point& p,const std::string& status) {
    f<<seed<<','<<path<<','<<mode<<','<<t<<','<<species<<','<<charge<<','<<p.x<<','<<p.y<<','<<p.z<<','<<status<<'\n';
  };
  json ledger=json::array();
  for (std::size_t ev=0;ev<c.simulation.nEvents;++ev) {
    Point start; start.x=gRandom->Uniform(-g.pitchCm/2,g.pitchCm/2); start.y=gRandom->Uniform(-g.pitchCm/2,g.pitchCm/2);
    start.z=g.zTopCuTop+gRandom->Uniform(1.e-5,g.dDriftCm-1.e-5);
    if (!electron.DriftElectron(start.x,start.y,start.z,0.) || electron.GetElectrons().empty()) throw std::runtime_error("Electron drift failed");
    const auto raw=electron.GetElectrons().front(); Track el{raw.path,raw.status};
    if(el.points.size()<2 || Surface(g,el.points.back(),el.status).rfind("failed_",0)==0)
      throw std::runtime_error("Unresolved original electron transport");
    const bool corrected=boundary.Clip(el);if(corrected)++correctedElectrons;
    const auto& p=el.points;
    if (p.size()<2 || Surface(g,p.back(),el.status).rfind("failed_",0)==0) throw std::runtime_error("Unresolved electron path");
    std::vector<double> ra(p.size()-1),re(p.size()-1),w(p.size(),1.),ci(p.size(),0.),ca(p.size(),0.);
    for (std::size_t j=0;j+1<p.size();++j) {
      // Midpoint quadrature avoids evaluating the field exactly on BEM panels.
      auto q=At(p,(p[j].t+p[j+1].t)/2.); double ex,ey,ez; Garfield::Medium* m=nullptr; int st;
      sensor.ElectricField(q.x,q.y,q.z,ex,ey,ez,m,st);
      if (st || !m) {
        auto describe = [&](const Point& v) {
          double fx=0.,fy=0.,fz=0.; Garfield::Medium* medium=nullptr; int status=0;
          sensor.ElectricField(v.x,v.y,v.z,fx,fy,fz,medium,status);
          auto* geometric=detector.Component().GetMedium(v.x,v.y,v.z);
          return json{{"x",v.x},{"y",v.y},{"z",v.z},{"t",v.t},{"field_status",status},
                      {"field_medium",medium?medium->GetName():"null"},
                      {"geometry_medium",geometric?geometric->GetName():"null"},
                      {"field",{fx,fy,fz}}};
        };
        WriteJsonFile(out/"transport_failure.json",{{"seed",seed},{"path",ev},{"segment",j},
          {"electron_status",el.status},{"terminal_segment",j+2==p.size()},
          {"start",describe(p[j])},{"midpoint",describe(q)},{"end",describe(p[j+1])}});
        throw std::runtime_error("Invalid transport field at quadrature point; see transport_failure.json");
      }
      double a=0.,e=0.,vx=0.,vy=0.,vz=0.;
      const bool coefficients=m->ElectronTownsend(ex,ey,ez,0.,0.,0.,a) &&
        m->ElectronAttachment(ex,ey,ez,0.,0.,0.,e) && m->ElectronVelocity(ex,ey,ez,0.,0.,0.,vx,vy,vz);
      if(!coefficients || !std::isfinite(a+e+vx+vy+vz) || a<0. || e<0.)
        throw std::runtime_error("Invalid diagnostic transport coefficients");
      const double dl=std::sqrt(vx*vx+vy*vy+vz*vz)*(p[j+1].t-p[j].t);
      ra[j]=std::max(0.,a)*dl; re[j]=std::max(0.,e)*dl;
      const auto step=Grow(w[j],ra[j],re[j]); w[j+1]=step.end; ci[j+1]=ci[j]+step.ions; ca[j+1]=ca[j]+step.attached;
    }
    // Sample the two positive measures independently; exact integration maintains
    // 1 + ionisations = free electrons + attachment charge at every snapshot.
    const auto primary=drift(start,false);
    struct Born { Point b; Track mobile; double weight; };
    auto births = [&](const std::vector<double>& cum,bool negative,double until) {
      std::vector<Born> v;
      std::vector<double> limit=cum;
      std::size_t n=p.size()-1;
      double fraction=1.;
      if (until<p.back().t) {
        n=static_cast<std::size_t>(std::upper_bound(p.begin(),p.end(),until,[](double t,const Point& q){return t<q.t;})-p.begin()-1);
        fraction=(until-p[n].t)/(p[n+1].t-p[n].t);
        const auto step=Grow(w[n],ra[n]*fraction,re[n]*fraction);
        limit.resize(n+2); limit[n+1]=cum[n]+(negative?step.attached:step.ions);
      }
      const double total=limit.back(); if(total<=0.) return v;
      for(std::size_t k=0;k<K;++k) {
        const double u=(k+gRandom->Uniform())/K*total;
        std::size_t j=static_cast<std::size_t>(std::upper_bound(limit.begin(),limit.end(),u)-limit.begin()-1);
        j=std::min(j,limit.size()-2);
        const double span=(j==n?fraction:1.); const double r=(ra[j]-re[j])*span;
        const double u2=gRandom->Uniform();
        const double frac=span*(std::abs(r)<1.e-8?u2:std::log1p(u2*std::expm1(r))/r);
        Point b=At(p,p[j].t+frac*(p[j+1].t-p[j].t));
        v.push_back({b,drift(b,negative),total/K});
      }
      return v;
    };
    // Reuse complete trajectories when all births precede the first sample;
    // otherwise sample the truncated birth measure for each observation time.
    std::vector<Born> allI,allA;
    const bool early=p.back().t<=ts.front();
    if(early){allI=births(ci,false,ts.back());allA=births(ca,true,ts.back());}
    for(double t:ts) {
      auto ip=early?allI:births(ci,false,t); auto ap=early?allA:births(ca,true,t);
      double we=w.back();
      if(t<p.back().t){const auto j=static_cast<std::size_t>(std::upper_bound(p.begin(),p.end(),t,[](double v,const Point& q){return v<q.t;})-p.begin()-1); const double frac=(t-p[j].t)/(p[j+1].t-p[j].t);we=Grow(w[j],ra[j]*frac,re[j]*frac).end;}
      const auto ep=At(p,t),pp=At(primary.points,t);
      double ni=0.,na=0.;for(const auto& b:ip)ni+=b.weight;for(const auto& b:ap)na+=b.weight;
      const double residual=1.+ni-we-na;
      if(std::abs(residual)>1.e-9*std::max(1.,we+na))throw std::runtime_error("Snapshot charge conservation failed");
      for(const char* mode:{"fixed","mobile"}) {
        emit(ev,mode,t,"electron",-we,ep,t<p.back().t?"moving":Surface(g,ep,el.status));
        emit(ev,mode,t,"primary_ion",1.,pp,t<primary.points.back().t?"moving":Surface(g,pp,primary.status));
        for(const auto& b:ip){auto q=At(b.mobile.points,t);emit(ev,mode,t,"ion",b.weight,q,t<b.mobile.points.back().t?"moving":Surface(g,q,b.mobile.status));}
        for(const auto& b:ap){const bool fixed=std::string(mode)=="fixed";auto q=fixed?b.b:At(b.mobile.points,t);emit(ev,mode,t,"negative_ion",-b.weight,q,fixed?"attached":(t<b.mobile.points.back().t?"moving":Surface(g,q,b.mobile.status)));}
      }
    }
    ledger.push_back({{"path",ev},{"electron_weight",w.back()},{"ions",ci.back()},{"attachment",ca.back()},{"electron_status",el.status},{"collection_boundary_corrected",corrected}});
    std::cout<<"[glass export] path "<<ev+1<<"/"<<c.simulation.nEvents<<std::endl;
  }
  f.close();if(!f)throw std::runtime_error("Snapshot write failed");
  fs::rename(out/"charge_snapshots.csv.partial",out/"charge_snapshots.csv");
  WriteJsonFile(out/"transport_ledger.json",ledger);
  WriteJsonFile(out/"collection_boundary_checks.json",{{"corrected_electrons",correctedElectrons},{"corrected_ions",correctedIons},{"gas_side_tolerance_cm",1.e-8}});
}

std::vector<std::string> Split(const std::string& s) {
  std::vector<std::string> v;std::istringstream in(s);std::string x;while(std::getline(in,x,','))v.push_back(x);return v;
}
void Replay(const CliOptions& o,const Config& c,const fs::path& out) {
  const auto d=Settings(o);const std::string model=d.value("model",std::string("metal"));
  if(model!="metal" && model!="glass")throw std::runtime_error("model must be metal or glass");
  const double thick=model=="glass"?d.value("glass_thickness_mm",0.8)*0.1:0.;
  const double eps=d.value("glass_epsilon_r",8.);
  if(thick<0. || eps<1. || !std::isfinite(eps) || !std::isfinite(thick))throw std::runtime_error("Invalid glass parameters");
  const auto recorded=ReadJsonFile(o.glassReplay.parent_path()/"input_config.json");
  const auto requested=ReadJsonFile(o.configPath);
  if(recorded.at("geometry")!=requested.at("geometry") || recorded.at("fields")!=requested.at("fields"))
    throw std::runtime_error("Replay geometry/fields differ from the recorded transport");
  MediumMagboltz gas; // Weighting geometry needs a gas permittivity, no transport tables.
  ThgemDetector detector(c.geometry,c.fields,gas,thick,eps,true);
  // Do not use the transport's primitive-averaged far-copy approximation for
  // signal potentials: it can violate the contacted conductor's boundary value.
  detector.Component().SetWtFldPrimAfter(-1);
  if(!detector.Initialise())throw std::runtime_error("Weighting solve failed");
  auto& comp=detector.Component();const auto& g=detector.Geom();
  std::ifstream input(o.glassReplay);std::string line;std::getline(input,line);
  if(line!="seed,path,attachment,time_ns,species,charge_e,x_cm,y_cm,z_cm,status")throw std::runtime_error("Unsupported snapshot schema");
  using Key=std::tuple<int,int,std::string,double>;
  std::map<Key,std::array<double,4>> charges;
  std::map<std::tuple<double,double,double,std::string>,std::array<double,4>> cache;
  double maxPartition=0.; std::size_t processed=0;
  while(std::getline(input,line)) {
    if (++processed % 10000 == 0) std::cout<<"[glass replay] records "<<processed<<std::endl;
    auto v=Split(line);if(v.size()!=10)throw std::runtime_error("Malformed snapshot row");
    Point p;p.x=std::stod(v[6]);p.y=std::stod(v[7]);p.z=std::stod(v[8]);const double q=std::stod(v[5]);
    const auto key=std::make_tuple(p.x,p.y,p.z,v[9]);auto it=cache.find(key);
    if(it==cache.end()) {
      std::array<double,4> phi{};
      if(v[9]=="drift")phi[3]=1.;
      else if(v[9]=="anode" && thick==0.)phi[0]=1.;
      else {
        // Evaluate a continuous potential from the gas side, avoiding a point
        // exactly on a boundary panel. The glass front is NOT pinned to 1 V.
        if(v[9]=="anode")p.z=g.zAnode+1.e-7;
        for(std::size_t k=0;k<4;++k)phi[k]=comp.WeightingPotential(p.x,p.y,p.z,labels[k]);
      }
      const double sum=std::accumulate(phi.begin(),phi.end(),0.);
      maxPartition=std::max(maxPartition,std::abs(sum-1.));
      for(double value:phi)if(!std::isfinite(value))throw std::runtime_error("Non-finite weighting potential");
      it=cache.emplace(key,phi).first;
    }
    const Key record{std::stoi(v[0]),std::stoi(v[1]),v[2],std::stod(v[3])};
    for(std::size_t k=0;k<4;++k)charges[record][k]+=q*it->second[k];
  }
  if(charges.empty())throw std::runtime_error("No snapshot records");
  std::ofstream f(out/"signal_charges.csv");f<<std::setprecision(17)<<"seed,path,attachment,time_ns,anode_e,top_e,bottom_e,drift_e\n";
  for(const auto& [key,q]:charges){const auto& [s,p,m,t]=key;f<<s<<','<<p<<','<<m<<','<<t;for(double x:q)f<<','<<x;f<<'\n';}
  const double rear=thick>0.?comp.WeightingPotential(0.,0.,g.zAnode-thick+1.e-7,"anode"):1.;
  WriteJsonFile(out/"weighting_checks.json",{{"max_partition_residual",maxPartition},{"rear_weighting_potential",rear},{"model",model},{"glass_thickness_mm",thick*10.},{"glass_epsilon_r",eps},{"full_rear_face_ohmic_contact",true}});
}

void Probe(const CliOptions& o,const Config& c,const fs::path& out) {
  MediumMagboltz gas;
  ThgemDetector detector(c.geometry,c.fields,gas);
  if(!detector.Initialise())throw std::runtime_error("Probe field solve failed");
  const auto data=Settings(o).at("transport_probe");
  auto point=[](const json& v){Point p;p.x=v.at("x");p.y=v.at("y");p.z=v.at("z");p.t=v.at("t");return p;};
  const auto a=point(data.at("start")),b=point(data.at("end"));
  Track track{{a,b},Garfield::StatusAlive};CollectionBoundary boundary(detector);
  const bool clipped=boundary.Clip(track);
  const auto endpoint=track.points.back();auto mid=At(track.points,(a.t+endpoint.t)/2.);
  double ex,ey,ez;Garfield::Medium* m=nullptr;int status;
  detector.Component().ElectricField(mid.x,mid.y,mid.z,ex,ey,ez,m,status);
  if(!clipped || status || !m || !m->IsDriftable() || endpoint.t<=a.t || endpoint.t>=b.t)
    throw std::runtime_error("Material-crossing regression failed");
  Track periodic{{a,b},Garfield::StatusAlive};
  for(auto& p:periodic.points)p.x+=detector.Geom().pitchCm;
  if(!boundary.Clip(periodic) || std::abs(periodic.points.back().t-endpoint.t)>1.e-8)
    throw std::runtime_error("Periodic material crossing regression failed");
  const Point inside=At(std::vector<Point>{a,endpoint},a.t+.25*(endpoint.t-a.t));
  Track clear{{a,inside},Garfield::StatusAlive};
  if(boundary.Clip(clear))throw std::runtime_error("Gas-only segment was changed");
  WriteJsonFile(out/"transport_probe.json",{{"periodic_check",true},{"gas_only_unchanged",true},{"clipped",clipped},{"field_status",status},
    {"endpoint",{{"x",endpoint.x},{"y",endpoint.y},{"z",endpoint.z},{"t",endpoint.t}}}});
}

void Planar(const CliOptions& o,const Config& c,const fs::path& out) {
  const auto d=Settings(o);const double t=d.value("glass_thickness_mm",0.8)*0.1;
  const double gap=c.geometry.inductionGapMm*0.1,eps=d.value("glass_epsilon_r",8.);
  if(t<0. || gap<=0. || eps<1. || !std::isfinite(t+gap+eps))throw std::runtime_error("Invalid planar parameters");
  MediumMagboltz gas;MediumPlastic glass(eps);MediumConductor cu;GeometrySimple geo;geo.SetMedium(&gas);
  const double h=1.;SolidBox top(0,0,gap,h,h,0.),rear(0,0,-t,h,h,0.);
  top.SetBoundaryPotential(0.);rear.SetBoundaryPotential(0.);top.SetLabel("top");rear.SetLabel("anode");
  geo.AddSolid(&top,&cu);geo.AddSolid(&rear,&cu);
  std::unique_ptr<SolidBox> slab;
  if(t>0.){slab=std::make_unique<SolidBox>(0,0,-t/2,h,h,t/2);slab->SetBoundaryDielectric();geo.AddSolid(slab.get(),&glass);}
  ComponentNeBem3d comp;comp.SetGeometry(&geo);comp.SetPeriodicityX(2*h);comp.SetPeriodicityY(2*h);
  comp.SetPeriodicCopies(9,9,0);comp.SetTargetElementSize(0.1);comp.SetMinMaxNumberOfElements(3,10);comp.UseLUInversion();
  if(!comp.Initialise())throw std::runtime_error("Planar solve failed");
  const double expected=gap/(gap+t/eps);
  const double actual=comp.WeightingPotential(0.,0.,1.e-7,"anode");
  const double rearValue=comp.WeightingPotential(0.,0.,-t+1.e-7,"anode");
  double integral=0.; const double dz=(gap-2.e-7)/100.;
  for(int j=0;j<100;++j){double ex,ey,ez;comp.WeightingField(0.,0.,1.e-7+(j+.5)*dz,ex,ey,ez,"anode");integral-=ez*dz;}
  const double endpoint=comp.WeightingPotential(0.,0.,gap-1.e-7,"anode")-actual;
  double balance=0.;
  for(const auto& rates:std::vector<std::array<double,2>>{{0.,0.},{.1,.1},{2.,.1},{.1,2.},{1.e-12,0.}}){auto v=Grow(3.,rates[0],rates[1]);balance=std::max(balance,std::abs(3.+v.ions-v.end-v.attached));}
  WriteJsonFile(out/"planar.json",{{"expected",expected},{"actual",actual},{"relative_error",std::abs(actual/expected-1.)},{"rear_value",rearValue},{"trajectory_charge",integral},{"endpoint_charge",endpoint},{"trajectory_relative_error",std::abs(integral-endpoint)/expected},{"growth_balance_residual",balance},{"full_rear_face_ohmic_contact",true}});
}
} // namespace glass_signal

int RunGlassDiagnostic(const CliOptions& o,Config c) {
  if(static_cast<int>(o.glassExport)+static_cast<int>(o.glassPlanar)+static_cast<int>(o.glassProbe)+static_cast<int>(!o.glassReplay.empty())!=1)
    throw std::runtime_error("Select exactly one glass diagnostic mode");
  const fs::path out=o.outDir/(o.runName.empty()?"glass_diagnostic":o.runName);
  EnsureDirectory(out);WriteJsonFile(out/"input_config.json",ReadJsonFile(o.configPath));
  if(o.glassExport)glass_signal::Export(o,c,out);
  else if(o.glassProbe)glass_signal::Probe(o,c,out);
  else if(o.glassPlanar)glass_signal::Planar(o,c,out);
  else glass_signal::Replay(o,c,out);
  return 0;
}
