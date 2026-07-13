// Garfield++ THGEM (Thick Gas Electron Multiplier) simulation
//
// Geometry : one THGEM plate — a dielectric (FR4/Kapton) foil, copper-clad on
//            both faces, pierced by a periodic array of cylindrical holes.
//            The plate lies in the x–y plane, drift axis is z:
//              z > 0  drift gap  → drift cathode (readout "cathode")
//              z ≈ 0  THGEM plate (top Cu, dielectric, bottom Cu)
//              z < 0  induction gap → anode pad (readout "anode")
//            A single square unit cell (one hole) is modelled and tiled with
//            neBEM mirror/periodic boundary conditions.
// Field    : solved in-process by ComponentNeBem3d (native boundary-element
//            method) — the hole field has no analytic form.  Electrode
//            potentials are derived from the physics fields:
//              V_anode = 0                         (reference)
//              V_botCu = −E_ind · d_ind
//              V_topCu = V_botCu − ΔV_THGEM
//              V_drift = V_topCu − E_drift · d_drift
//            so electrons drift down (−z) toward the most-positive anode.
// Gas      : Ar:CO2 (configurable), 1 atm, 293.15 K, transported by Magboltz.
// Source   : N = E/W primary electrons placed at a configurable height in the
//            drift gap above the plate; a single representative electron is
//            transported by AvalancheMicroscopic and the result scaled by N.
// Readout  : (1) anode pad  ("anode"),  (2) drift cathode ("cathode").
//            Induced signals via Shockley–Ramo weighting fields — neBEM
//            computes the weighting field of each labelled electrode natively.
//
// Adapted from projects/tgc/src/tgc_sim.cc; the gas, avalanche, signal, track
// and I/O machinery is shared, the wire-chamber field engine is replaced.

#include <TCanvas.h>
#include <TDirectory.h>
#include <TFile.h>
#include <TGraph.h>
#include <TGraphErrors.h>
#include <TH1D.h>
#include <TH2D.h>
#include <TProfile.h>
#include <TROOT.h>
#include <TRandom.h>
#include <TStyle.h>
#include <TTree.h>

#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstddef>
#include <ctime>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <map>
#include <memory>
#include <numeric>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <string_view>
#include <vector>

#include "Garfield/AvalancheMC.hh"
#include "Garfield/AvalancheMicroscopic.hh"
#include "Garfield/Component.hh"
#include "Garfield/ComponentGrid.hh"
#include "Garfield/ComponentNeBem3d.hh"
#include "Garfield/ComponentUser.hh"
#include "Garfield/FundamentalConstants.hh"
#include "Garfield/GarfieldConstants.hh"
#include "Garfield/GeometrySimple.hh"
#include "Garfield/MediumConductor.hh"
#include "Garfield/MediumMagboltz.hh"
#include "Garfield/MediumPlastic.hh"
#include "Garfield/Random.hh"
#include "Garfield/RandomEngineRoot.hh"
#include "Garfield/Sensor.hh"
#include "Garfield/Solid.hh"
#include "Garfield/SolidBox.hh"
#include "Garfield/SolidHole.hh"
#include "nlohmann/json.hpp"

namespace fs = std::filesystem;

namespace {

using Garfield::AvalancheMC;
using Garfield::AvalancheMicroscopic;
using Garfield::ComponentGrid;
using Garfield::ComponentNeBem3d;
using Garfield::ComponentUser;
using Garfield::GeometrySimple;
using Garfield::MediumConductor;
using Garfield::MediumMagboltz;
using Garfield::MediumPlastic;
using Garfield::Sensor;
using Garfield::Solid;
using Garfield::SolidBox;
using Garfield::SolidHole;
using json = nlohmann::json;


// ─── Configuration structs ────────────────────────────────────────────────────

struct GeometryConfig {
  double holeDiameterUm    = 500.0;   // hole diameter [µm]
  double holePitchUm       = 800.0;   // centre-to-centre hole spacing [µm] (square array)
  double plateThicknessUm  = 400.0;   // dielectric foil thickness [µm]
  double copperThicknessUm = 35.0;    // copper cladding thickness per face [µm]
  double rimUm             = 0.0;     // etched dielectric clearance (v1: 0 → straight hole)
  double driftGapMm        = 3.0;     // top-Cu surface → drift cathode [mm]
  double inductionGapMm    = 2.0;     // bottom-Cu surface → anode pad [mm]
  std::string dielectric   = "fr4";   // "fr4" | "kapton"
  // neBEM mesh / solver controls (rarely touched; coarser = faster, less accurate)
  double targetElementSizeUm = 100.0; // target boundary-element size [µm]
  int    minElements         = 3;     // min elements along a primitive edge
  int    maxElements         = 5;     // max elements along a primitive edge
  int    periodicCopies      = 7;     // neBEM periodic copies; >=7 needed so the
                                       // tiled cathode/anode patches approximate an
                                       // infinite plane (fewer -> reversed drift field)
  int    holeSectors         = 4;     // circle approximation (2=square, 3=octagon, …)
  // Transport field is sampled from neBEM onto this grid (fast interpolation
  // during the avalanche).  The grid spans ~1.4 cells in x/y and drift→anode in z.
  int    gridNx              = 41;    // grid nodes across x (and y)
  int    gridNz              = 161;   // grid nodes along z (drift axis)
};

struct FieldConfig {
  double eDriftKvcm     = 0.5;    // drift-gap field [kV/cm]
  double deltaVThgemV   = 800.0;  // voltage across the THGEM (top→bottom Cu) [V]
  double eInductionKvcm = 3.0;    // induction-gap field [kV/cm]
};

struct SourceConfig {
  double energyKeV                                          = 5.9;
  // Height of the primary electrons above the THGEM top surface, in the drift
  // gap [mm].  nullopt → uniform random over the drift gap per event.
  std::optional<std::vector<double>> fixedDistMm =
      std::vector<double>{1.0};
  // Fixed x-position within the unit cell [cm]; nullopt → random over the cell.
  // (y is always sampled uniformly over the cell.)
  std::optional<std::vector<double>> fixedXCmList;
};

struct GasConfig {
  std::string gas1           = "ar";
  double      frac1          = 70.0;
  std::string gas2           = "co2";
  std::string ionSpecies     = "co2";
  double temperatureK        = 293.15;
  double pressureTorr        = 760.0;
  bool   enablePenning       = true;
  int    nCollisions         = 2;
  double maxElectronEnergyEV = 2000.0;  // EFINAL of the Magboltz table (keys the .gas file name)
  // Ceiling of the microscopic collision-rate table.  AvalancheMicroscopic samples
  // every transport step against the *maximum* collision rate over the whole energy
  // grid (MediumMagboltz::m_cfNull), rejecting the rest as null collisions.  A ceiling
  // far above the energies the electrons actually reach therefore costs a proportional
  // number of wasted steps.  A THGEM's peak field (~20 kV/cm) keeps electrons at a few
  // eV, so this is set well below the TGC-inherited 2 keV table EFINAL.  Applied after
  // LoadGasFile, which rebuilds the rate table without touching the transport tables.
  double transportMaxEnergyEV = 200.0;
  int    nFieldPoints        = 10;
  double eFieldMinVcm        = 100.0;
  double eFieldMaxVcm        = 400000.0;
  double wValueEV            = 26.0;
};

struct SimulationConfig {
  std::size_t nEvents          = 100;
  std::size_t maxAvalancheSize = 200000;
  double      timeWindowNs     = 200.0;
  double      timeStepNs       = 0.5;
  bool        enableIonDrift   = false;
  bool        storeDriftLines  = false;
  double      ionMaxStepUm     = 5.0;
  // Wall-clock safety bound for ion drift (AvalancheMC).  Ions are ~1000x slower
  // than electrons; distance-stepping bounds a normal ion by geometry, and this
  // time window is the backstop that terminates an ion trapped at a field
  // stagnation point.  1 ms comfortably exceeds a full drift-gap ion transit
  // (~0.6 ms) while capping a stuck/oscillating ion at ~a thousand steps.
  double      ionTimeWindowNs  = 1.0e6;
  // Cap on the number of avalanche ions actually back-drifted per event (0 =
  // no cap).  Ions drift up, away from the anode, where its weighting field is
  // zero, so they contribute ~nothing to the anode signal — but transporting all
  // of them dominates the runtime at high gain.  A modest cap keeps gain runs
  // fast; raise it (or set 0) for ion-backflow studies.
  std::size_t maxIonsDrifted   = 200;
  int         randomSeed       = 0;
};

// ─── 3D-visualisation display limits ─────────────────────────────────────────
constexpr std::size_t kMaxDispIonPaths = 100;  // ion drift paths saved per event
constexpr std::size_t kMaxDispCloudPts = 500;  // avalanche-cloud points saved per event

// The transport grid spans exactly one unit cell in x/y (half-width = pitch/2)
// and is tiled with mirror periodicity, so charges diffusing past a cell edge
// re-enter the neighbouring cell instead of being lost (as in the Garfield GEM
// examples).  The hole is centred in the cell, so the cell boundary is a mirror
// plane.
constexpr double kGridHalfSpanFactor = 0.5;

struct Config {
  GeometryConfig   geometry;
  FieldConfig      fields;
  SourceConfig     source;
  GasConfig        gas;
  SimulationConfig simulation;
};

// ─── Per-distance summary ─────────────────────────────────────────────────────
// Field names retain the tgc "cathode_top" slot for ROOT-schema compatibility
// with the shared GUI; in THGEM v1 the cathode_top channel is always zero.

struct DistanceSummary {
  std::optional<double> distanceMm;           // nullopt = random per event
  std::optional<double> xPositionCm;          // nullopt = random per event
  std::size_t nEvents               = 0;
  std::size_t nInteracted           = 0;
  double      interactionFraction   = 0.;
  double      meanAnodeChargeFC     = 0.;
  double      rmsAnodeChargeFC      = 0.;
  double      semAnodeChargeFC      = 0.;
  double      meanCathodeChargeFC      = 0.;
  double      rmsCathodeChargeFC       = 0.;
  double      semCathodeChargeFC       = 0.;
  double      meanCathodeTopChargeFC   = 0.;
  double      rmsCathodeTopChargeFC    = 0.;
  double      semCathodeTopChargeFC    = 0.;
  double      meanChargeRatio       = 0.;
  double      rmsChargeRatio        = 0.;
  double      semChargeRatio        = 0.;
  double      meanPrimaryElectrons  = 0.;
  double      meanAvalancheSize     = 0.;
};

// ─── Utility ──────────────────────────────────────────────────────────────────

std::string FormatNumber(double v, int precision = 4) {
  std::ostringstream ss;
  ss << std::fixed << std::setprecision(precision) << v;
  std::string s = ss.str();
  while (!s.empty() && s.back() == '0') s.pop_back();
  if (!s.empty() && s.back() == '.') s.pop_back();
  return s.empty() ? "0" : s;
}

std::string FileSafeNumber(double v) {
  std::string s = FormatNumber(v);
  std::replace(s.begin(), s.end(), '.', 'p');
  std::replace(s.begin(), s.end(), '-', 'm');
  return s;
}

std::string DeriveGasFileName(const GasConfig& g) {
  auto I = [](double v) {
    return std::to_string(static_cast<long long>(std::llround(v)));
  };
  const int    efKv    = static_cast<int>(std::llround(g.eFieldMaxVcm / 1000.0));
  const int    efMinV  = static_cast<int>(std::llround(g.eFieldMinVcm));
  const double frac2 = 100.0 - g.frac1;
  const std::string prefix = g.gas1 + I(g.frac1) + "_" + g.gas2 + "_" + I(frac2);
  return prefix
       + "_T"  + I(g.temperatureK)
       + "_P"  + I(g.pressureTorr)
       + "_Ee" + I(g.maxElectronEnergyEV)
       + "_Ef" + std::to_string(efMinV) + "v-" + std::to_string(efKv) + "k"
       + "_n"  + std::to_string(g.nFieldPoints)
       + "_c"  + std::to_string(g.nCollisions)
       + (g.enablePenning ? "_pen" : "_nopen")
       + ".gas";
}

void EnsureDirectory(const fs::path& p) { fs::create_directories(p); }

/// Relative permittivity of a named dielectric foil material.
double DielectricEpsR(const std::string& material) {
  if (material == "fr4") return 4.6;
  if (material == "kapton") return 3.5;
  return 4.0;  // generic plastic fallback
}

template <typename T>
double Mean(const std::vector<T>& v) {
  if (v.empty()) return 0.;
  return std::accumulate(v.begin(), v.end(), 0.0) / static_cast<double>(v.size());
}

template <typename T>
double Rms(const std::vector<T>& v, double mean) {
  if (v.size() < 2) return 0.;
  double var = 0.;
  for (const auto& x : v) { double d = static_cast<double>(x) - mean; var += d * d; }
  return std::sqrt(var / static_cast<double>(v.size()));
}

double Sem(double rms, std::size_t n) {
  return n < 2 ? 0. : rms / std::sqrt(static_cast<double>(n));
}

// ─── JSON helpers ─────────────────────────────────────────────────────────────

[[noreturn]] void ThrowJsonTypeError(const std::initializer_list<std::string_view>& path,
                                     std::string_view expect) {
  std::string msg = "JSON error at '";
  bool first = true;
  for (auto p : path) { if (!first) msg += '.'; first = false; msg += std::string(p); }
  msg += "': expected " + std::string(expect) + ".";
  throw std::runtime_error(msg);
}

const json* FindMember(const json& obj, std::string_view key,
                       const std::initializer_list<std::string_view>& path) {
  if (!obj.is_object()) ThrowJsonTypeError(path, "an object");
  auto it = obj.find(std::string(key));
  return it == obj.end() ? nullptr : &(*it);
}

const json* FindSection(const json& obj, std::string_view key) {
  auto* p = FindMember(obj, key, {key});
  if (p && !p->is_object()) ThrowJsonTypeError({key}, "an object");
  return p;
}

double ReadDouble(const json& obj, std::string_view sec, std::string_view key, double fb) {
  auto* v = FindMember(obj, key, {sec, key});
  if (!v) return fb;
  if (!v->is_number()) ThrowJsonTypeError({sec, key}, "a number");
  return v->get<double>();
}

int ReadInt(const json& obj, std::string_view sec, std::string_view key, int fb) {
  auto* v = FindMember(obj, key, {sec, key});
  if (!v) return fb;
  if (!v->is_number_integer()) ThrowJsonTypeError({sec, key}, "an integer");
  return v->get<int>();
}

std::size_t ReadSizeT(const json& obj, std::string_view sec, std::string_view key, std::size_t fb) {
  auto* v = FindMember(obj, key, {sec, key});
  if (!v) return fb;
  if (!v->is_number_integer() && !v->is_number_unsigned())
    ThrowJsonTypeError({sec, key}, "a non-negative integer");
  auto val = v->get<long long>();
  if (val < 0) throw std::runtime_error("Expected non-negative integer at key '" + std::string(key) + "'");
  return static_cast<std::size_t>(val);
}

bool ReadBool(const json& obj, std::string_view sec, std::string_view key, bool fb) {
  auto* v = FindMember(obj, key, {sec, key});
  if (!v) return fb;
  if (!v->is_boolean()) ThrowJsonTypeError({sec, key}, "a boolean");
  return v->get<bool>();
}

std::string ReadString(const json& obj, std::string_view sec, std::string_view key,
                       const std::string& fb) {
  auto* v = FindMember(obj, key, {sec, key});
  if (!v) return fb;
  if (!v->is_string()) ThrowJsonTypeError({sec, key}, "a string");
  return v->get<std::string>();
}

json ReadJsonFile(const fs::path& p) {
  std::ifstream s(p);
  if (!s) throw std::runtime_error("Cannot open JSON file: " + p.string());
  try { return json::parse(s); }
  catch (const json::parse_error& e) {
    throw std::runtime_error("JSON parse error in '" + p.string() + "': " + e.what());
  }
}

void WriteJsonFile(const fs::path& p, const json& payload) {
  std::ofstream s(p);
  if (!s) throw std::runtime_error("Cannot write JSON file: " + p.string());
  s << std::setw(2) << payload << '\n';
}

// ─── CLI ──────────────────────────────────────────────────────────────────────

struct CliOptions {
  fs::path configPath{"config/default_thgem.json"};
  fs::path outDir{"results"};
  std::string runName;                    // empty = auto-generate from config
  std::optional<double> singleDistanceMm;
};

[[noreturn]] void PrintUsageAndExit(const char* prog, int code) {
  std::ostream& out = code == 0 ? std::cout : std::cerr;
  out << "Usage: " << prog << " [options]\n"
         "  --config <path>    JSON config file (default: config/default_thgem.json)\n"
         "  --out    <dir>     Output directory (default: results)\n"
         "  --run-name <name>  Subdirectory name under --out (default: auto)\n"
         "  --distance <mm>    Run only this drift-gap height (overrides config list)\n"
         "  --help             Show this message\n";
  std::exit(code);
}

CliOptions ParseCli(int argc, char* argv[]) {
  CliOptions opts;
  for (int i = 1; i < argc; ++i) {
    std::string arg = argv[i];
    if (arg == "--config") {
      if (i + 1 >= argc) PrintUsageAndExit(argv[0], 1);
      opts.configPath = argv[++i];
    } else if (arg == "--out") {
      if (i + 1 >= argc) PrintUsageAndExit(argv[0], 1);
      opts.outDir = argv[++i];
    } else if (arg == "--run-name") {
      if (i + 1 >= argc) PrintUsageAndExit(argv[0], 1);
      opts.runName = argv[++i];
    } else if (arg == "--distance") {
      if (i + 1 >= argc) PrintUsageAndExit(argv[0], 1);
      opts.singleDistanceMm = std::stod(argv[++i]);
    } else if (arg == "--help" || arg == "-h") {
      PrintUsageAndExit(argv[0], 0);
    } else {
      throw std::runtime_error("Unknown argument: " + arg);
    }
  }
  return opts;
}

// ─── Config loading ───────────────────────────────────────────────────────────

Config LoadConfig(const fs::path& path) {
  if (!fs::exists(path))
    throw std::runtime_error("Configuration file not found: " + path.string());
  const json root = ReadJsonFile(path);
  if (!root.is_object()) ThrowJsonTypeError({"<root>"}, "a JSON object");

  Config cfg;

  if (const auto* g = FindSection(root, "geometry")) {
    cfg.geometry.holeDiameterUm    = ReadDouble(*g, "geometry", "hole_diameter_um",    cfg.geometry.holeDiameterUm);
    cfg.geometry.holePitchUm       = ReadDouble(*g, "geometry", "hole_pitch_um",       cfg.geometry.holePitchUm);
    cfg.geometry.plateThicknessUm  = ReadDouble(*g, "geometry", "plate_thickness_um",  cfg.geometry.plateThicknessUm);
    cfg.geometry.copperThicknessUm = ReadDouble(*g, "geometry", "copper_thickness_um", cfg.geometry.copperThicknessUm);
    cfg.geometry.rimUm             = ReadDouble(*g, "geometry", "rim_um",              cfg.geometry.rimUm);
    cfg.geometry.driftGapMm        = ReadDouble(*g, "geometry", "drift_gap_mm",        cfg.geometry.driftGapMm);
    cfg.geometry.inductionGapMm    = ReadDouble(*g, "geometry", "induction_gap_mm",    cfg.geometry.inductionGapMm);
    cfg.geometry.dielectric        = ReadString(*g, "geometry", "dielectric_material", cfg.geometry.dielectric);
    cfg.geometry.targetElementSizeUm = ReadDouble(*g, "geometry", "target_element_size_um", cfg.geometry.targetElementSizeUm);
    cfg.geometry.minElements       = ReadInt   (*g, "geometry", "min_elements",        cfg.geometry.minElements);
    cfg.geometry.maxElements       = ReadInt   (*g, "geometry", "max_elements",        cfg.geometry.maxElements);
    cfg.geometry.periodicCopies    = ReadInt   (*g, "geometry", "periodic_copies",     cfg.geometry.periodicCopies);
    cfg.geometry.holeSectors       = ReadInt   (*g, "geometry", "hole_sectors",        cfg.geometry.holeSectors);
    cfg.geometry.gridNx            = ReadInt   (*g, "geometry", "grid_nx",             cfg.geometry.gridNx);
    cfg.geometry.gridNz            = ReadInt   (*g, "geometry", "grid_nz",             cfg.geometry.gridNz);
  }

  if (const auto* f = FindSection(root, "fields")) {
    cfg.fields.eDriftKvcm     = ReadDouble(*f, "fields", "e_drift_kvcm",     cfg.fields.eDriftKvcm);
    cfg.fields.deltaVThgemV   = ReadDouble(*f, "fields", "delta_v_thgem_V",  cfg.fields.deltaVThgemV);
    cfg.fields.eInductionKvcm = ReadDouble(*f, "fields", "e_induction_kvcm", cfg.fields.eInductionKvcm);
  }

  if (const auto* s = FindSection(root, "source")) {
    cfg.source.energyKeV    = ReadDouble(*s, "source", "energy_keV", cfg.source.energyKeV);
    {
      auto* dl = FindMember(*s, "source_distances_mm", {"source", "source_distances_mm"});
      if (dl && dl->is_array()) {
        cfg.source.fixedDistMm = std::vector<double>{};
        for (auto& v : *dl) cfg.source.fixedDistMm->push_back(v.get<double>());
      } else {
        cfg.source.fixedDistMm = std::nullopt;  // random per event
      }
    }
    auto* xpList = FindMember(*s, "x_positions_cm", {"source", "x_positions_cm"});
    if (xpList && xpList->is_array()) {
      cfg.source.fixedXCmList = std::vector<double>{};
      for (auto& v : *xpList)
        cfg.source.fixedXCmList->push_back(v.get<double>());
    } else {
      cfg.source.fixedXCmList = std::nullopt;
    }
  }

  if (const auto* g = FindSection(root, "gas")) {
    cfg.gas.gas1       = ReadString(*g, "gas", "gas1",               cfg.gas.gas1);
    cfg.gas.frac1      = ReadDouble(*g, "gas", "gas1_fraction_pct",  cfg.gas.frac1);
    cfg.gas.gas2       = ReadString(*g, "gas", "gas2",               cfg.gas.gas2);
    cfg.gas.ionSpecies = ReadString(*g, "gas", "ion_species",        cfg.gas.ionSpecies);
    cfg.gas.temperatureK  = ReadDouble(*g, "gas", "temperature_K",       cfg.gas.temperatureK);
    cfg.gas.pressureTorr  = ReadDouble(*g, "gas", "pressure_Torr",       cfg.gas.pressureTorr);
    cfg.gas.enablePenning = ReadBool  (*g, "gas", "enable_penning",       cfg.gas.enablePenning);
    cfg.gas.nCollisions         = ReadInt   (*g, "gas", "n_magboltz_collisions",  cfg.gas.nCollisions);
    cfg.gas.maxElectronEnergyEV = ReadDouble(*g, "gas", "max_electron_energy_eV", cfg.gas.maxElectronEnergyEV);
    cfg.gas.transportMaxEnergyEV = ReadDouble(*g, "gas", "transport_max_energy_eV",
                                              cfg.gas.transportMaxEnergyEV);
    cfg.gas.nFieldPoints        = ReadInt   (*g, "gas", "n_field_points",         cfg.gas.nFieldPoints);
    cfg.gas.eFieldMinVcm        = ReadDouble(*g, "gas", "e_field_min_vcm",        cfg.gas.eFieldMinVcm);
    cfg.gas.eFieldMaxVcm        = ReadDouble(*g, "gas", "e_field_max_vcm",        cfg.gas.eFieldMaxVcm);
    cfg.gas.wValueEV            = ReadDouble(*g, "gas", "w_value_eV",             cfg.gas.wValueEV);
  }

  if (const auto* s = FindSection(root, "simulation")) {
    cfg.simulation.nEvents          = ReadSizeT (*s, "simulation", "n_events",          cfg.simulation.nEvents);
    cfg.simulation.maxAvalancheSize = ReadSizeT (*s, "simulation", "max_avalanche_size", cfg.simulation.maxAvalancheSize);
    cfg.simulation.timeWindowNs     = ReadDouble(*s, "simulation", "time_window_ns",     cfg.simulation.timeWindowNs);
    cfg.simulation.timeStepNs       = ReadDouble(*s, "simulation", "time_step_ns",       cfg.simulation.timeStepNs);
    cfg.simulation.enableIonDrift   = ReadBool  (*s, "simulation", "enable_ion_drift",   cfg.simulation.enableIonDrift);
    cfg.simulation.storeDriftLines  = ReadBool  (*s, "simulation", "store_drift_lines",  cfg.simulation.storeDriftLines);
    cfg.simulation.ionMaxStepUm     = ReadDouble(*s, "simulation", "ion_max_step_um",    cfg.simulation.ionMaxStepUm);
    cfg.simulation.ionTimeWindowNs  = ReadDouble(*s, "simulation", "ion_time_window_ns", cfg.simulation.ionTimeWindowNs);
    cfg.simulation.maxIonsDrifted   = ReadSizeT (*s, "simulation", "max_ions_drifted",   cfg.simulation.maxIonsDrifted);
    cfg.simulation.randomSeed       = ReadInt   (*s, "simulation", "random_seed",        cfg.simulation.randomSeed);
  }

  // ── Validation ───────────────────────────────────────────────────────────────
  const auto& gm = cfg.geometry;
  if (gm.holeDiameterUm    <= 0.) throw std::runtime_error("geometry.hole_diameter_um must be positive");
  if (gm.holePitchUm       <= 0.) throw std::runtime_error("geometry.hole_pitch_um must be positive");
  if (gm.holeDiameterUm    >= gm.holePitchUm)
    throw std::runtime_error("geometry.hole_diameter_um must be smaller than hole_pitch_um");
  if (gm.plateThicknessUm  <= 0.) throw std::runtime_error("geometry.plate_thickness_um must be positive");
  if (gm.copperThicknessUm <  0.) throw std::runtime_error("geometry.copper_thickness_um must be >= 0");
  if (gm.rimUm             <  0.) throw std::runtime_error("geometry.rim_um must be >= 0");
  if (gm.rimUm             >  0.)
    throw std::runtime_error("geometry.rim_um > 0 (etched rim) is not supported yet; set 0");
  if (gm.driftGapMm        <= 0.) throw std::runtime_error("geometry.drift_gap_mm must be positive");
  if (gm.inductionGapMm    <= 0.) throw std::runtime_error("geometry.induction_gap_mm must be positive");
  if (gm.dielectric != "fr4" && gm.dielectric != "kapton")
    throw std::runtime_error("geometry.dielectric_material must be 'fr4' or 'kapton'");
  if (gm.targetElementSizeUm <= 0.) throw std::runtime_error("geometry.target_element_size_um must be positive");
  if (gm.minElements < 1 || gm.maxElements < gm.minElements)
    throw std::runtime_error("geometry.min_elements/max_elements invalid (need 1 <= min <= max)");
  if (gm.periodicCopies < 0) throw std::runtime_error("geometry.periodic_copies must be >= 0");
  if (gm.holeSectors < 2) throw std::runtime_error("geometry.hole_sectors must be >= 2");
  if (gm.gridNx < 4 || gm.gridNz < 4)
    throw std::runtime_error("geometry.grid_nx/grid_nz must be >= 4");
  if (cfg.fields.deltaVThgemV <= 0.) throw std::runtime_error("fields.delta_v_thgem_V must be positive");
  if (cfg.fields.eDriftKvcm    < 0.) throw std::runtime_error("fields.e_drift_kvcm must be >= 0");
  if (cfg.fields.eInductionKvcm< 0.) throw std::runtime_error("fields.e_induction_kvcm must be >= 0");

  if (cfg.source.fixedDistMm.has_value() && cfg.source.fixedDistMm->empty())
    throw std::runtime_error("source.source_distances_mm must not be empty when set");
  if (cfg.gas.frac1 <= 0. || cfg.gas.frac1 >= 100.)
    throw std::runtime_error("gas.gas1_fraction_pct must be in (0, 100)");
  if (cfg.gas.temperatureK     <= 0.)  throw std::runtime_error("gas.temperature_K must be positive");
  if (cfg.gas.pressureTorr     <= 0.)  throw std::runtime_error("gas.pressure_Torr must be positive");
  if (cfg.gas.transportMaxEnergyEV <= 0.)
    throw std::runtime_error("gas.transport_max_energy_eV must be positive");
  if (cfg.simulation.nEvents   == 0)   throw std::runtime_error("simulation.n_events must be at least 1");
  if (cfg.simulation.timeWindowNs <= 0.) throw std::runtime_error("simulation.time_window_ns must be positive");
  if (cfg.simulation.timeStepNs   <= 0.) throw std::runtime_error("simulation.time_step_ns must be positive");
  if (cfg.simulation.randomSeed   <  0)  throw std::runtime_error("simulation.random_seed must be >= 0");

  return cfg;
}

// ─── Gas setup ────────────────────────────────────────────────────────────────

static void ExportGasProps(MediumMagboltz& gas, const std::string& outPath,
                           const std::string& ionMobFile = "") {
  std::vector<double> efields, bfields, angles;
  gas.GetFieldGrid(efields, bfields, angles);

  std::ofstream f(outPath);
  if (!f) {
    std::cerr << "  Warning: could not write gas properties to " << outPath << "\n";
    return;
  }
  if (!ionMobFile.empty()) {
    const auto sep = ionMobFile.find_last_of("/\\");
    const std::string base = (sep == std::string::npos)
                             ? ionMobFile : ionMobFile.substr(sep + 1);
    f << "# ion_mobility: " << base << "\n";
  }
  f << "e_field_Vcm,vd_cm_per_us,alpha_per_cm,eta_per_cm,"
       "dl_sqrtcm,dt_sqrtcm,v_ion_cm_per_us,mu_ion_cm2_per_Vus\n";

  for (double E : efields) {
    double vx = 0, vy = 0, vz = 0;
    gas.ElectronVelocity(E, 0, 0, 0, 0, 0, vx, vy, vz);
    double alpha = 0, eta = 0, dl = 0, dt = 0;
    gas.ElectronTownsend(E, 0, 0, 0, 0, 0, alpha);
    gas.ElectronAttachment(E, 0, 0, 0, 0, 0, eta);
    gas.ElectronDiffusion(E, 0, 0, 0, 0, 0, dl, dt);

    double v_ion = 0, mu_ion = 0;
    double vix = 0, viy = 0, viz = 0;
    if (gas.IonVelocity(E, 0, 0, 0, 0, 0, vix, viy, viz)) {
      v_ion  = std::abs(vix) * 1.e3;
      mu_ion = (E > 0.) ? v_ion / E : 0.;
    }

    f << std::scientific << std::setprecision(6)
      << E       << ","
      << vx * 1.e3 << ","
      << alpha   << ","
      << eta     << ","
      << dl      << ","
      << dt      << ","
      << v_ion   << ","
      << mu_ion  << "\n";
  }
  std::cout << "  Gas properties exported to: " << outPath << "\n";
}

std::string DriftStatusToString(const int st) {
  switch (st) {
    case Garfield::StatusAlive: return "alive";
    case Garfield::StatusLeftDriftArea: return "left drift area";
    case Garfield::StatusTooManySteps: return "too many steps";
    case Garfield::StatusCalculationAbandoned: return "calculation abandoned";
    case Garfield::StatusLeftDriftMedium: return "left drift medium";
    case Garfield::StatusAttached: return "attached";
    case Garfield::StatusSharpKink: return "sharp kink";
    case Garfield::StatusRecombined: return "recombined";
    case Garfield::StatusHitPlane: return "hit plane";
    case Garfield::StatusBelowTransportCut: return "below transport cut";
    case Garfield::StatusOutsideTimeWindow: return "outside time window";
    default: return "status " + std::to_string(st);
  }
}

std::string SetupGas(MediumMagboltz& gas, const GasConfig& cfg,
                     const bool requireIonMobility) {
  gas.SetTemperature(cfg.temperatureK);
  gas.SetPressure(cfg.pressureTorr);

  // Gas tables and their _props.csv sidecars live in gas/ (keeps the project root tidy).
  EnsureDirectory("gas");
  const std::string gasFile = (fs::path("gas") / DeriveGasFileName(cfg)).string();

  if (fs::exists(gasFile)) {
    std::cout << "  Loading gas table from: " << gasFile << "\n";
    gas.LoadGasFile(gasFile);
  } else {
    std::cout << "  Gas file not found: " << gasFile << "\n"
              << "  Running Magboltz for " << cfg.nFieldPoints
              << " field points from " << static_cast<int>(cfg.eFieldMinVcm)
              << " to " << static_cast<int>(cfg.eFieldMaxVcm) << " V/cm ...\n";
    gas.SetMaxElectronEnergy(cfg.maxElectronEnergyEV);   // EFINAL of the generated table
    gas.SetFieldGrid(cfg.eFieldMinVcm, cfg.eFieldMaxVcm, cfg.nFieldPoints, /*logspacing=*/true);
    gas.GenerateGasTable(cfg.nCollisions, /*verbose=*/false);
    gas.WriteGasFile(gasFile);
    std::cout << "  Gas table saved to: " << gasFile << "\n";
  }

  // Cap the microscopic collision-rate table well below the transport-table EFINAL.
  // AvalancheMicroscopic draws every step from the *maximum* rate over the whole energy
  // grid and rejects the surplus as null collisions, so an oversized ceiling costs a
  // proportional number of wasted steps.  Re-run after LoadGasFile: SetMaxElectronEnergy
  // only forces the rate table to be rebuilt; the loaded transport tables are untouched.
  // If an electron ever exceeds the ceiling Garfield raises it automatically.
  gas.SetMaxElectronEnergy(cfg.transportMaxEnergyEV);
  std::cout << "  Collision-rate ceiling: " << cfg.transportMaxEnergyEV
            << " eV (table EFINAL " << cfg.maxElectronEnergyEV << " eV)"
            << ", null-collision rate = " << gas.GetElectronNullCollisionRate(0) << " /ns\n";

  if (cfg.enablePenning) {
    if (!gas.EnablePenningTransfer())
      std::cerr << "  Warning: Penning transfer could not be enabled.\n";
    else
      std::cout << "  Penning transfer enabled.\n";
  }

  const char* garfieldInstall = std::getenv("GARFIELD_INSTALL");
  std::string loadedMob;
  std::string ionUpper = cfg.ionSpecies;
  std::transform(ionUpper.begin(), ionUpper.end(), ionUpper.begin(), ::toupper);
  if (garfieldInstall) {
    const std::string mobFile = std::string(garfieldInstall) +
                                "/share/Garfield/Data/IonMobility_"
                                + ionUpper + "+_" + ionUpper + ".txt";
    if (fs::exists(mobFile)) {
      gas.LoadIonMobility(mobFile);
      std::cout << "  " << ionUpper << "+ ion mobility loaded.\n";
      loadedMob = mobFile;
    } else {
      std::cerr << "  Warning: IonMobility_" << ionUpper << "+_" << ionUpper
                << ".txt not found at " << mobFile << "\n";
    }
  } else {
    std::cerr << "  Warning: GARFIELD_INSTALL not set; ion mobility not loaded.\n";
  }

  if (requireIonMobility && loadedMob.empty()) {
    throw std::runtime_error(
        "simulation.enable_ion_drift=true requires an ion mobility table for "
        + ionUpper + "+. Set GARFIELD_INSTALL so Garfield++ can find "
        + "share/Garfield/Data/IonMobility_" + ionUpper + "+_" + ionUpper
        + ".txt, or disable simulation.enable_ion_drift.");
  }

  const std::string propsFile = gasFile.substr(0, gasFile.size() - 4) + "_props.csv";
  ExportGasProps(gas, propsFile, loadedMob);
  return loadedMob;
}

// ─── THGEM geometry (neBEM) ───────────────────────────────────────────────────

// Computed cell dimensions [cm] and derived electrode potentials [V].
struct ThgemGeom {
  double rHoleCm    = 0.;
  double pitchCm    = 0.;   // full cell size (square)
  double tDielCm    = 0.;
  double tCuCm      = 0.;
  double dDriftCm   = 0.;
  double dIndCm     = 0.;
  double epsDiel    = 4.6;
  double zDielHalf  = 0.;   // dielectric extends [-zDielHalf, +zDielHalf]
  double zTopCuTop  = 0.;   // outer surface of the top copper
  double zBotCuBot  = 0.;   // outer surface of the bottom copper
  double zDrift     = 0.;   // drift cathode plate
  double zAnode     = 0.;   // anode readout plate
  double vDrift     = 0.;
  double vTopCu     = 0.;
  double vBotCu     = 0.;
  double vAnode     = 0.;
};

// Owns the media, solids, geometry and neBEM component of the THGEM cell.
// Lives for the whole run (neBEM references the geometry during field lookups).
class ThgemDetector {
 public:
  ThgemDetector(const GeometryConfig& g, const FieldConfig& f, MediumMagboltz& gas) {
    geom_ = ComputeGeom(g, f);
    diel_.SetDielectricConstant(geom_.epsDiel);

    const double hx = geom_.pitchCm / 2.0;   // cell half-width in x and y
    const double hy = geom_.pitchCm / 2.0;
    const auto sec  = static_cast<std::size_t>(g.holeSectors);

    // Drift cathode: fixed-potential plate one drift gap above the plate.
    auto drift = std::make_unique<SolidBox>(0., 0., geom_.zDrift, hx, hy, 0.);
    drift->SetBoundaryPotential(geom_.vDrift);
    geo_.AddSolid(drift.get(), &cu_);
    solids_.push_back(std::move(drift));

    // Top copper cladding (box with hole), sitting on top of the dielectric.
    const double zTopCu = geom_.zDielHalf + geom_.tCuCm / 2.0;
    auto topCu = std::make_unique<SolidHole>(0., 0., zTopCu, geom_.rHoleCm,
                                             geom_.rHoleCm, hx, hy, geom_.tCuCm / 2.0);
    topCu->SetSectors(sec);
    topCu->SetBoundaryPotential(geom_.vTopCu);
    geo_.AddSolid(topCu.get(), &cu_);
    solids_.push_back(std::move(topCu));

    // Dielectric foil (box with hole), centred at z = 0.
    auto diel = std::make_unique<SolidHole>(0., 0., 0., geom_.rHoleCm,
                                            geom_.rHoleCm, hx, hy, geom_.zDielHalf);
    diel->SetSectors(sec);
    diel->SetBoundaryDielectric();
    geo_.AddSolid(diel.get(), &diel_);
    solids_.push_back(std::move(diel));

    // Bottom copper cladding (box with hole).
    const double zBotCu = -(geom_.zDielHalf + geom_.tCuCm / 2.0);
    auto botCu = std::make_unique<SolidHole>(0., 0., zBotCu, geom_.rHoleCm,
                                             geom_.rHoleCm, hx, hy, geom_.tCuCm / 2.0);
    botCu->SetSectors(sec);
    botCu->SetBoundaryPotential(geom_.vBotCu);
    geo_.AddSolid(botCu.get(), &cu_);
    solids_.push_back(std::move(botCu));

    // Anode readout plate one induction gap below the plate.  Its Ramo
    // weighting field is supplied analytically by a ComponentUser (see
    // SetupAnodeWeighting); neBEM only needs it as a fixed-potential electrode.
    auto anode = std::make_unique<SolidBox>(0., 0., geom_.zAnode, hx, hy, 0.);
    anode->SetBoundaryPotential(geom_.vAnode);
    geo_.AddSolid(anode.get(), &cu_);
    solids_.push_back(std::move(anode));

    // The gas fills all space not occupied by a solid.
    geo_.SetMedium(&gas);
    gasPtr_ = &gas;

    // neBEM solver: one periodic cell tiled in x and y.
    nebem_.SetGeometry(&geo_);
    nebem_.SetTargetElementSize(g.targetElementSizeUm * 1.e-4);
    nebem_.SetMinMaxNumberOfElements(static_cast<std::size_t>(g.minElements),
                                     static_cast<std::size_t>(g.maxElements));
    nebem_.SetPeriodicityX(geom_.pitchCm);
    nebem_.SetPeriodicityY(geom_.pitchCm);
    const auto pc = static_cast<std::size_t>(g.periodicCopies);
    nebem_.SetPeriodicCopies(pc, pc, 0);
    // Performance: evaluate full elements only for the central cell / first ring,
    // and cheap primitive-averaged properties for the more distant periodic
    // copies.  Without this neBEM evaluates every element for every field call
    // (the default), which makes avalanches and the field-map dump intractably
    // slow.  The near-field (inside the hole, where the avalanche lives) is
    // unaffected.
    nebem_.SetPrimAfter(1);
    nebem_.SetWtFldPrimAfter(1);
    nebem_.UseLUInversion();
  }

  bool Initialise() { return nebem_.Initialise(); }
  ComponentNeBem3d& Component() { return nebem_; }
  const ThgemGeom& Geom() const { return geom_; }

  // True if (x, y, z) is in the gas, i.e. not inside a copper or dielectric
  // solid.  Used to tag absorbing nodes when sampling the transport grid
  // (ComponentGrid carries no material information of its own).
  bool InGas(const double x, const double y, const double z) const {
    return geo_.GetMedium(x, y, z) == gasPtr_;
  }

 private:
  static ThgemGeom ComputeGeom(const GeometryConfig& g, const FieldConfig& f) {
    ThgemGeom o;
    o.rHoleCm   = g.holeDiameterUm  * 0.5e-4;   // µm diameter → cm radius
    o.pitchCm   = g.holePitchUm     * 1.e-4;
    o.tDielCm   = g.plateThicknessUm  * 1.e-4;
    o.tCuCm     = g.copperThicknessUm * 1.e-4;
    o.dDriftCm  = g.driftGapMm * 0.1;
    o.dIndCm    = g.inductionGapMm * 0.1;
    o.epsDiel   = DielectricEpsR(g.dielectric);

    o.zDielHalf = o.tDielCm / 2.0;
    o.zTopCuTop = o.zDielHalf + o.tCuCm;
    o.zBotCuBot = -(o.zDielHalf + o.tCuCm);
    o.zDrift    = o.zTopCuTop + o.dDriftCm;
    o.zAnode    = o.zBotCuBot - o.dIndCm;

    // Physics fields → electrode potentials (anode reference, electrons drift −z).
    const double eDriftVcm = f.eDriftKvcm     * 1000.0;
    const double eIndVcm   = f.eInductionKvcm * 1000.0;
    o.vAnode = 0.0;
    o.vBotCu = o.vAnode - eIndVcm * o.dIndCm;
    o.vTopCu = o.vBotCu - f.deltaVThgemV;
    o.vDrift = o.vTopCu - eDriftVcm * o.dDriftCm;
    return o;
  }

  MediumConductor cu_;
  MediumPlastic   diel_;
  GeometrySimple  geo_;
  ComponentNeBem3d nebem_;
  std::vector<std::unique_ptr<Solid>> solids_;
  ThgemGeom geom_;
  Garfield::Medium* gasPtr_ = nullptr;
};

// Sample the solved field on an x–z slice through the hole centre (y = 0) and
// on the hole axis, and write it to the ROOT file for the GUI's E-Field tab.
void DumpFieldMap(Garfield::Component& cmp, const ThgemGeom& g, TDirectory* dir) {
  if (!dir) return;
  constexpr int nx = 81, nz = 161;
  const double xLo = -g.pitchCm, xHi = g.pitchCm;   // two cells (via periodicity)
  const double zLo = g.zAnode,   zHi = g.zDrift;

  TH2D hMag("h_field_mag", "THGEM |E| through hole centre;x [cm];z [cm]",
            nx, xLo, xHi, nz, zLo, zHi);
  TH2D hPot("h_potential", "THGEM potential through hole centre;x [cm];z [cm]",
            nx, xLo, xHi, nz, zLo, zHi);
  hMag.SetDirectory(nullptr);
  hPot.SetDirectory(nullptr);

  std::vector<double> axZ, axE, axV;
  axZ.reserve(nz); axE.reserve(nz); axV.reserve(nz);

  for (int iz = 0; iz < nz; ++iz) {
    const double z = zLo + (iz + 0.5) * (zHi - zLo) / nz;
    for (int ix = 0; ix < nx; ++ix) {
      const double x = xLo + (ix + 0.5) * (xHi - xLo) / nx;
      double ex = 0, ey = 0, ez = 0, v = 0;
      int status = 0;
      Garfield::Medium* m = nullptr;
      cmp.ElectricField(x, 0., z, ex, ey, ez, v, m, status);
      const double emag = std::sqrt(ex * ex + ey * ey + ez * ez) / 1000.0;  // kV/cm
      hMag.SetBinContent(ix + 1, iz + 1, emag);
      hPot.SetBinContent(ix + 1, iz + 1, v);
    }
    // On-axis profile (x = y = 0).
    double ex = 0, ey = 0, ez = 0, v = 0; int status = 0;
    Garfield::Medium* m = nullptr;
    cmp.ElectricField(0., 0., z, ex, ey, ez, v, m, status);
    axZ.push_back(z);
    axE.push_back(std::sqrt(ex * ex + ey * ey + ez * ez) / 1000.0);
    axV.push_back(v);
  }

  TGraph gAxisE(static_cast<int>(axZ.size()), axZ.data(), axE.data());
  gAxisE.SetName("g_axis_field");
  gAxisE.SetTitle("On-axis |E|;z [cm];|E| [kV/cm]");
  TGraph gAxisV(static_cast<int>(axZ.size()), axZ.data(), axV.data());
  gAxisV.SetName("g_axis_potential");
  gAxisV.SetTitle("On-axis potential;z [cm];V [V]");

  dir->cd();
  hMag.Write("h_field_mag");
  hPot.Write("h_potential");
  gAxisE.Write("g_axis_field");
  gAxisV.Write("g_axis_potential");
  std::cout << "  Field map dumped (" << nx << "×" << nz << " x–z slice, "
            << "on-axis profile).\n";
}

// Sample the neBEM field onto the grid nodes and write a ComponentGrid "xyz"
// cache file with a trailing in-solid flag (1 = gas, 0 = inside copper/dielectric
// → absorbing).  The flag is what lets electrons terminate on the electrodes:
// ComponentGrid has no material map, so without it charges drift through metal.
void SampleFieldToFile(ComponentNeBem3d& cmp, const ThgemDetector& det,
                       const ThgemGeom& g, const GeometryConfig& gc,
                       const double gxy, const std::string& file) {
  // Write atomically via a temp file + rename: an interrupted or crashing sample
  // must never leave a truncated file that looks like a valid cache on the next run.
  const std::string tmp = file + ".part";
  {
    std::ofstream out(tmp);
    if (!out) throw std::runtime_error("Cannot write field cache: " + tmp);
    out << std::setprecision(8);
    const int NX = gc.gridNx, NZ = gc.gridNz;
    const double dxy = 2. * gxy / std::max(NX - 1, 1);
    const double dz  = (g.zDrift - g.zAnode) / std::max(NZ - 1, 1);
    const std::size_t total = static_cast<std::size_t>(NX) * NX * NZ;
    std::size_t done = 0, nextPct = 20;
    for (int i = 0; i < NX; ++i) {
      const double x = -gxy + i * dxy;
      for (int j = 0; j < NX; ++j) {
        const double y = -gxy + j * dxy;
        for (int k = 0; k < NZ; ++k) {
          const double z = g.zAnode + k * dz;
          double ex = 0, ey = 0, ez = 0, v = 0; int status = 0;
          Garfield::Medium* m = nullptr;
          cmp.ElectricField(x, y, z, ex, ey, ez, v, m, status);
          const int flag = det.InGas(x, y, z) ? 1 : 0;
          out << x << ' ' << y << ' ' << z << ' '
              << ex << ' ' << ey << ' ' << ez << ' ' << v << ' ' << flag << '\n';
          if (++done * 100 >= nextPct * total) {
            std::cout << "    sampling " << nextPct << "%\n";
            nextPct += 20;
          }
        }
      }
    }
    out.flush();
    if (!out) throw std::runtime_error("Write error while sampling field cache: " + tmp);
  }  // close the stream before renaming
  fs::rename(tmp, file);
}

// Count the lines in a file.  Used to detect a truncated field cache: a short
// file is not rejected by ComponentGrid::LoadElectricField (it silently leaves the
// missing nodes at zero, which would run the avalanche in a bogus ~zero field), so
// the node count must be validated against the grid before the cache is trusted.
std::size_t CountFileLines(const std::string& file) {
  std::ifstream in(file);
  std::size_t n = 0;
  std::string line;
  while (std::getline(in, line)) ++n;
  return n;
}

// Cache filename for the sampled transport field, keyed by the geometry, fields
// and grid resolution (mirrors the .gas caching): identical parameters reuse the
// neBEM sample instead of re-solving.
std::string DeriveFieldCacheName(const GeometryConfig& g, const FieldConfig& f) {
  auto I = [](double v) {
    return std::to_string(static_cast<long long>(std::llround(v)));
  };
  std::ostringstream ss;
  ss << "thgem_field_h" << I(g.holeDiameterUm) << "_p" << I(g.holePitchUm)
     << "_t" << I(g.plateThicknessUm) << "_c" << I(g.copperThicknessUm)
     << "_dg" << FileSafeNumber(g.driftGapMm) << "_ig" << FileSafeNumber(g.inductionGapMm)
     << "_" << g.dielectric
     << "_dV" << I(f.deltaVThgemV) << "_Ed" << FileSafeNumber(f.eDriftKvcm)
     << "_Ei" << FileSafeNumber(f.eInductionKvcm)
     << "_g" << g.gridNx << "x" << g.gridNz
     << "_s" << g.holeSectors << "_pc" << g.periodicCopies << "_v2.txt";
  return ss.str();
}

// Analytic parallel-plate Ramo weighting field of the anode pad, valid in the
// induction gap (zAnode < z < zBotCuBot) and screened to zero above the bottom
// copper.  A collected electron drifting the full gap induces exactly one unit
// of charge; charges still inside/above the THGEM induce nothing (bottom-copper
// screening).  A fast, physically-motivated v1 stand-in for a full neBEM
// weighting solve on the (structured) anode.
void SetupAnodeWeighting(ComponentUser& w, const ThgemGeom& g) {
  const double zA = g.zAnode;
  const double zB = g.zBotCuBot;
  const double d  = zB - zA;   // = induction gap [cm]
  w.SetWeightingPotential(
      [zA, zB, d](const double, const double, const double z) -> double {
        if (z <= zA) return 1.0;
        if (z >= zB) return 0.0;
        return (zB - z) / d;
      }, "anode");
  w.SetWeightingField(
      [zA, zB, d](const double, const double, const double z,
                  double& wx, double& wy, double& wz) {
        wx = 0.; wy = 0.;
        wz = (z > zA && z < zB) ? (1.0 / d) : 0.0;
      }, "anode");
}

// ─── Sensor setup ─────────────────────────────────────────────────────────────

void SetupSensor(Sensor& sensor, ComponentGrid& grid, ComponentUser& wAnode,
                 const ThgemGeom& g, const SimulationConfig& sim) {
  sensor.AddComponent(&grid);            // transport field + drift medium
  sensor.AddElectrode(&wAnode, "anode"); // analytic anode weighting field

  const std::size_t nBins =
      static_cast<std::size_t>(std::round(sim.timeWindowNs / sim.timeStepNs));
  sensor.SetTimeWindow(0., sim.timeStepNs, nBins);

  // Wide in x/y (mirror periodicity supplies the field for any cell), bounded in
  // z to the drift cathode → anode span: charges are collected when they leave in
  // z.  Several pitches of lateral room let the avalanche/diffusion spread, as in
  // the Garfield GEM examples.
  const double xy = 3.0 * g.pitchCm;
  sensor.SetArea(-xy, -xy, g.zAnode, xy, xy, g.zDrift);
}

// ─── Per-distance simulation loop ─────────────────────────────────────────────

DistanceSummary RunDistancePoint(const Config& cfg, const ThgemGeom& g,
                                 std::optional<double> distOptMm,
                                 Sensor& sensor, TDirectory* distDir,
                                 std::optional<double> fixedXCm = std::nullopt) {
  const auto& sim = cfg.simulation;

  const double cellHalfCm = g.pitchCm / 2.0;          // unit-cell half-width
  const double driftGapMm = g.dDriftCm * 10.0;        // full drift gap in mm

  const std::size_t nBins =
      static_cast<std::size_t>(std::round(sim.timeWindowNs / sim.timeStepNs));

  // ── Histograms ──────────────────────────────────────────────────────────────
  TH1D hAnodeQ("h_anode_charge",
               "Induced charge on anode;Q_{anode} [fC];Events", 200, 0., 0.);
  TH1D hCathodeQ("h_cathode_charge",
                 "Induced charge on cathode;Q_{cathode} [fC];Events", 200, 0., 0.);
  TH1D hRatio("h_ratio_charge",
              "Charge ratio;Q_{cathode}/Q_{anode};Events", 100, 0., 2.);
  TH1D hNprimary("h_n_primary_electrons",
                 "Primary electrons per event;N_{e,primary};Events", 400, -0.5, 399.5);
  TH1D hAvalSize("h_avalanche_size",
                 "Total avalanche size;N_{e,total};Events", 200, 0., 0.);
  TH1D hCathodeTopQ("h_cathode_top_charge",
                   "Induced charge on cathode_top;Q_{cathode\\_top} [fC];Events", 200, 0., 0.);

  TProfile pAnodeSignal("p_anode_signal",
                        "Mean anode signal;t [ns];#LTi_{anode}#GT [fC/ns]",
                        static_cast<int>(nBins), 0., sim.timeWindowNs);
  TProfile pCathodeSignal("p_cathode_signal",
                          "Mean cathode signal;t [ns];#LTi_{cathode}#GT [fC/ns]",
                          static_cast<int>(nBins), 0., sim.timeWindowNs);
  TProfile pCathodeTopSignal("p_cathode_top_signal",
                             "Mean cathode_top signal;t [ns];#LTi_{cathode\\_top}#GT [fC/ns]",
                             static_cast<int>(nBins), 0., sim.timeWindowNs);
  TProfile pAnodeElec("p_anode_electron",
                      "Mean anode e^{-} signal;t [ns];#LTi_{anode,e}#GT [fC/ns]",
                      static_cast<int>(nBins), 0., sim.timeWindowNs);
  TProfile pAnodeIon("p_anode_ion",
                     "Mean anode ion signal;t [ns];#LTi_{anode,ion}#GT [fC/ns]",
                     static_cast<int>(nBins), 0., sim.timeWindowNs);
  TProfile pCathodeElec("p_cathode_electron",
                        "Mean cathode e^{-} signal;t [ns];#LTi_{cathode,e}#GT [fC/ns]",
                        static_cast<int>(nBins), 0., sim.timeWindowNs);
  TProfile pCathodeIon("p_cathode_ion",
                       "Mean cathode ion signal;t [ns];#LTi_{cathode,ion}#GT [fC/ns]",
                       static_cast<int>(nBins), 0., sim.timeWindowNs);
  // Amplifier profiles retained (zero in v1) for ROOT-schema compatibility.
  TProfile pAnodeAmp("p_anode_amp", "Mean anode amplifier output;t [ns];#LTV_{anode}#GT [mV]",
                     static_cast<int>(nBins), 0., sim.timeWindowNs);
  TProfile pCathodeAmp("p_cathode_amp", "Mean cathode amplifier output;t [ns];#LTV_{cathode}#GT [mV]",
                       static_cast<int>(nBins), 0., sim.timeWindowNs);
  TProfile pAnodeAmpInt("p_anode_amp_int", "Integrated anode amp output;t [ns];#LT#int V dt#GT [mV ns]",
                        static_cast<int>(nBins), 0., sim.timeWindowNs);
  TProfile pCathodeAmpInt("p_cathode_amp_int", "Integrated cathode amp output;t [ns];#LT#int V dt#GT [mV ns]",
                          static_cast<int>(nBins), 0., sim.timeWindowNs);

  for (TH1* h : std::initializer_list<TH1*>{
           &hAnodeQ, &hCathodeQ, &hCathodeTopQ, &hRatio, &hNprimary, &hAvalSize,
           &pAnodeSignal, &pCathodeSignal, &pCathodeTopSignal,
           &pAnodeElec, &pAnodeIon, &pCathodeElec, &pCathodeIon,
           &pAnodeAmp, &pCathodeAmp, &pAnodeAmpInt, &pCathodeAmpInt}) {
    h->SetDirectory(nullptr);
  }

  // ── Per-event signal tree ────────────────────────────────────────────────────
  TTree signalTree("t_signals", "Per-event signal waveforms");
  signalTree.SetDirectory(nullptr);
  std::vector<float> anodeSig(nBins, 0.f), cathodeSig(nBins, 0.f);
  std::vector<float> anodeSigE(nBins, 0.f), anodeSigI(nBins, 0.f);
  std::vector<float> cathodeSigE(nBins, 0.f), cathodeSigI(nBins, 0.f);
  std::vector<float> anodeAmp(nBins, 0.f), cathodeAmp(nBins, 0.f);
  std::vector<float> anodeAmpInt(nBins, 0.f), cathodeAmpInt(nBins, 0.f);
  std::vector<double> bufA(nBins), bufC(nBins);
  std::vector<double> bufAe(nBins), bufAi(nBins), bufCe(nBins), bufCi(nBins);
  int   evtId = 0;
  float evtQa = 0.f, evtQc = 0.f;
  signalTree.Branch("event",             &evtId, "event/I");
  signalTree.Branch("anode_charge_fC",   &evtQa, "anode_charge_fC/F");
  signalTree.Branch("cathode_charge_fC", &evtQc, "cathode_charge_fC/F");
  signalTree.Branch("anode",   &anodeSig);
  signalTree.Branch("cathode", &cathodeSig);
  signalTree.Branch("anode_e",   &anodeSigE);
  signalTree.Branch("anode_i",   &anodeSigI);
  signalTree.Branch("cathode_e", &cathodeSigE);
  signalTree.Branch("cathode_i", &cathodeSigI);
  signalTree.Branch("anode_amp",   &anodeAmp);
  signalTree.Branch("cathode_amp", &cathodeAmp);
  signalTree.Branch("anode_amp_int",   &anodeAmpInt);
  signalTree.Branch("cathode_amp_int", &cathodeAmpInt);

  // ── 3D track branches ────────────────────────────────────────────────────────
  std::vector<float> primaryX, primaryY, primaryZ;
  std::vector<float> cloudX,   cloudY,   cloudZ;
  std::vector<float> ionX,     ionY,     ionZ;
  std::vector<int>   ionNpts;
  signalTree.Branch("primary_x", &primaryX);
  signalTree.Branch("primary_y", &primaryY);
  signalTree.Branch("primary_z", &primaryZ);
  signalTree.Branch("cloud_x",   &cloudX);
  signalTree.Branch("cloud_y",   &cloudY);
  signalTree.Branch("cloud_z",   &cloudZ);
  signalTree.Branch("ion_x",     &ionX);
  signalTree.Branch("ion_y",     &ionY);
  signalTree.Branch("ion_z",     &ionZ);
  signalTree.Branch("ion_npts",  &ionNpts);

  // ── Transport objects ────────────────────────────────────────────────────────
  const int nPrimary = std::max(1,
      static_cast<int>(std::round(cfg.source.energyKeV * 1.e3 / cfg.gas.wValueEV)));

  AvalancheMicroscopic aval(&sensor);
  if (sim.maxAvalancheSize > 0) aval.EnableAvalancheSizeLimit(sim.maxAvalancheSize);
  if (sim.storeDriftLines) aval.EnableDriftLines(true);
  // Bound the *transport* in time.  Sensor::SetTimeWindow only bins the induced signal;
  // without this an electron that drifts slowly (or stalls) is tracked indefinitely.
  // Charges still in flight at the end of the window end as StatusOutsideTimeWindow.
  aval.SetTimeWindow(0., sim.timeWindowNs);

  // Ion drift uses AvalancheMC (Monte-Carlo drift) rather than DriftLineRKF: the
  // RKF integrator has no step-count or time bound, so a single ion near a field
  // stagnation point loops indefinitely (hang) with unbounded path storage (OOM).
  // AvalancheMC steps by a fixed distance (bounds a normal ion by geometry) and
  // honours a time window (SetTimeWindow), the backstop that terminates a trapped
  // ion — the same mechanism that bounds the electron avalanche above.
  std::optional<AvalancheMC> ionDrift;
  if (sim.enableIonDrift) {
    ionDrift.emplace(&sensor);
    ionDrift->EnableDriftLines(true);   // populate EndPoint::path for the 3D view
    if (sim.ionMaxStepUm > 0.) ionDrift->SetDistanceSteps(sim.ionMaxStepUm * 1.e-4);
    ionDrift->SetTimeWindow(0., sim.ionTimeWindowNs);
    std::cout << "  Ion drift: AvalancheMC, " << sim.ionMaxStepUm
              << " um steps, " << sim.ionTimeWindowNs << " ns time window.\n";
  }

  std::vector<double> anodeCharges, cathodeCharges, cathodeTopCharges, chargeRatios;
  std::vector<double> primaryCounts, avalancheSizes;
  anodeCharges.reserve(sim.nEvents);
  cathodeCharges.reserve(sim.nEvents);
  cathodeTopCharges.reserve(sim.nEvents);

  std::size_t nInteracted = 0;
  const std::size_t progressStep = std::max<std::size_t>(1, sim.nEvents / 10);
  const std::string distLabel = distOptMm.has_value()
      ? FormatNumber(*distOptMm) + " mm" : "random";

  // Primary-electron fate diagnostic: collection efficiency and attachment are the
  // two loss channels a THGEM lives or dies by, so tally, over the events, how many
  // multiply (ne > 1) and how each primary ends — its Garfield status combined with
  // where it stopped (in the hole, on the plate, in the drift gap, below the plate).
  std::size_t nMultiplied = 0;
  std::map<std::string, int> primaryFate;
  auto classifyEndZone = [&g](double xe, double ye, double ze) -> std::string {
    if (ze > g.zTopCuTop) return "in-gap";       // still above the plate
    if (ze < g.zBotCuBot) return "below-plate";  // through the hole toward the anode
    return (std::hypot(xe, ye) < g.rHoleCm) ? "in-hole" : "in-plate";
  };

  // ── Event loop ───────────────────────────────────────────────────────────────
  auto tEvent = std::chrono::steady_clock::now();
  for (std::size_t ev = 0; ev < sim.nEvents; ++ev) {
    sensor.ClearSignal();

    // Start position: (x, y) within the unit cell, z at the configured height
    // in the drift gap above the top-copper surface.  A fixed x pins y = 0, so
    // x = 0 lands on the hole axis (a deterministic on-axis scan); with x random
    // both coordinates are sampled over the cell (realistic collection).
    const double x0 = fixedXCm.has_value()
                          ? *fixedXCm
                          : gRandom->Uniform(-cellHalfCm, cellHalfCm);
    const double y0 = fixedXCm.has_value()
                          ? 0.0
                          : gRandom->Uniform(-cellHalfCm, cellHalfCm);

    const double heightMm = distOptMm.has_value()
                                ? *distOptMm
                                : gRandom->Uniform(0., driftGapMm);
    double z0 = g.zTopCuTop + heightMm * 0.1;   // mm → cm above top copper
    z0 = std::max(g.zTopCuTop + 1.e-4, std::min(g.zDrift - 1.e-4, z0));

    // Transport one representative electron and scale by nPrimary (see tgc note).
    ++nInteracted;
    hNprimary.Fill(nPrimary);
    primaryCounts.push_back(static_cast<double>(nPrimary));

    aval.AvalancheElectron(x0, y0, z0, 0., 0.1);  // 0.1 eV ≈ thermal
    int ne = 0, ni = 0;
    aval.GetAvalancheSize(ne, ni);
    const int totalAvalElectrons = ne * nPrimary;
    hAvalSize.Fill(static_cast<double>(totalAvalElectrons));
    avalancheSizes.push_back(static_cast<double>(totalAvalElectrons));

    const std::size_t nEp = aval.GetNumberOfElectronEndpoints();

    // Fate of this event's primary electron (endpoint 0 is track 0, the primary).
    if (ne > 1) ++nMultiplied;
    if (nEp > 0) {
      double fx0, fy0, fz0, ft0, fe0, fx1, fy1, fz1, ft1, fe1; int fst;
      aval.GetElectronEndpoint(0, fx0, fy0, fz0, ft0, fe0,
                                  fx1, fy1, fz1, ft1, fe1, fst);
      ++primaryFate[DriftStatusToString(fst) + " @ " + classifyEndZone(fx1, fy1, fz1)];
    }

    // Primary electron drift line (track 0).
    primaryX.clear(); primaryY.clear(); primaryZ.clear();
    {
      const std::size_t nPts = aval.GetNumberOfElectronDriftLinePoints(0);
      primaryX.reserve(nPts); primaryY.reserve(nPts); primaryZ.reserve(nPts);
      for (std::size_t ip = 0; ip < nPts; ++ip) {
        double px, py, pz, pt;
        aval.GetElectronDriftLinePoint(px, py, pz, pt, ip, /*track=*/0);
        primaryX.push_back(static_cast<float>(px));
        primaryY.push_back(static_cast<float>(py));
        primaryZ.push_back(static_cast<float>(pz));
      }
    }

    // Avalanche cloud: start positions of secondary electron tracks.
    cloudX.clear(); cloudY.clear(); cloudZ.clear();
    {
      const std::size_t nSec   = nEp > 0 ? nEp - 1 : 0;
      const std::size_t stride = (nSec > kMaxDispCloudPts && kMaxDispCloudPts > 0)
                                  ? nSec / kMaxDispCloudPts : 1;
      cloudX.reserve(std::min(nSec, kMaxDispCloudPts));
      for (std::size_t i = 1; i < nEp; i += stride) {
        double x0c, y0c, z0c, t0c, e0c, x1c, y1c, z1c, t1c, e1c; int stc;
        aval.GetElectronEndpoint(i, x0c, y0c, z0c, t0c, e0c,
                                    x1c, y1c, z1c, t1c, e1c, stc);
        cloudX.push_back(static_cast<float>(x0c));
        cloudY.push_back(static_cast<float>(y0c));
        cloudZ.push_back(static_cast<float>(z0c));
      }
    }

    // Back-drift the avalanche ions from where they were created; AvalancheMC
    // adds the Ramo-induced current to the sensor and (for the first
    // kMaxDispIonPaths) the drift-line path is extracted for 3D display.  Only the
    // first sim.maxIonsDrifted are transported (0 = all): ions drift away from the
    // anode and induce ~nothing on it, so this bounds the high-gain runtime without
    // changing the anode signal.  DriftIon clears its ion container each call, so
    // GetIons() holds exactly the ion just drifted (with its full trajectory).
    ionX.clear(); ionY.clear(); ionZ.clear(); ionNpts.clear();
    if (sim.enableIonDrift) {
      const std::size_t nIons = (sim.maxIonsDrifted > 0)
          ? std::min(nEp, sim.maxIonsDrifted) : nEp;
      for (std::size_t i = 0; i < nIons; ++i) {
        double xi0, yi0, zi0, ti0, ei0, xi1, yi1, zi1, ti1, ei1; int st;
        aval.GetElectronEndpoint(i, xi0, yi0, zi0, ti0, ei0,
                                    xi1, yi1, zi1, ti1, ei1, st);
        const bool ok = ionDrift->DriftIon(xi0, yi0, zi0, ti0);
        const auto& ions = ionDrift->GetIons();
        if (!ok || ions.empty()) {
          const int driftStatus =
              ions.empty() ? Garfield::StatusCalculationAbandoned : ions.front().status;
          std::ostringstream msg;
          msg << "Ion drift failed for event " << ev << ", height " << distLabel
              << ", ion " << i << "/" << nEp
              << " from (" << xi0 << ", " << yi0 << ", " << zi0 << ") cm"
              << " at t=" << ti0 << " ns; end status "
              << DriftStatusToString(driftStatus) << " (" << driftStatus << "). "
              << "Ensure GARFIELD_INSTALL exposes an ion mobility table for "
              << cfg.gas.ionSpecies << "+ or disable simulation.enable_ion_drift.";
          throw std::runtime_error(msg.str());
        }
        if (i < kMaxDispIonPaths) {
          const auto& path = ions.front().path;
          ionNpts.push_back(static_cast<int>(path.size()));
          for (const auto& pt : path) {
            ionX.push_back(static_cast<float>(pt.x));
            ionY.push_back(static_cast<float>(pt.y));
            ionZ.push_back(static_cast<float>(pt.z));
          }
        }
      }
    }

    // Bin the induced current [fC/ns] on the anode.  The cathode and cathode_top
    // channels are not read out in v1 (kept zero for ROOT-schema compatibility
    // with the shared GUI).
    for (std::size_t k = 0; k < nBins; ++k) {
      bufA[k]  = sensor.GetSignal("anode",   k);
      bufAe[k] = sensor.GetElectronSignal("anode", k);
      bufAi[k] = sensor.GetIonSignal     ("anode", k);
      bufC[k] = 0.; bufCe[k] = 0.; bufCi[k] = 0.;
    }

    double rawAnode = 0., rawCathode = 0.;
    for (std::size_t k = 0; k < nBins; ++k) {
      rawAnode   += bufA[k];
      rawCathode += bufC[k];
      const double t = (static_cast<double>(k) + 0.5) * sim.timeStepNs;
      pAnodeSignal.Fill(t,   bufA[k] * nPrimary);
      pCathodeSignal.Fill(t, bufC[k] * nPrimary);
      pCathodeTopSignal.Fill(t, 0.);
      pAnodeElec.Fill(t,   bufAe[k] * nPrimary);
      pAnodeIon.Fill(t,    bufAi[k] * nPrimary);
      pCathodeElec.Fill(t, bufCe[k] * nPrimary);
      pCathodeIon.Fill(t,  bufCi[k] * nPrimary);
      anodeSig[k]    = static_cast<float>(bufA[k] * nPrimary);
      cathodeSig[k]  = static_cast<float>(bufC[k] * nPrimary);
      anodeSigE[k]   = static_cast<float>(bufAe[k] * nPrimary);
      anodeSigI[k]   = static_cast<float>(bufAi[k] * nPrimary);
      cathodeSigE[k] = static_cast<float>(bufCe[k] * nPrimary);
      cathodeSigI[k] = static_cast<float>(bufCi[k] * nPrimary);
    }

    // Sign convention: the anode collects avalanche electrons → negate its raw
    // integral for the conventionally positive collected charge; the cathode
    // (drift plane) integral is kept as-is.
    const double qAnode      = -rawAnode   * sim.timeStepNs * nPrimary;  // [fC]
    const double qCathode    =  rawCathode * sim.timeStepNs * nPrimary;  // [fC]
    const double qCathodeTop =  0.;

    evtId = static_cast<int>(ev);
    evtQa = static_cast<float>(qAnode);
    evtQc = static_cast<float>(qCathode);
    signalTree.Fill();

    hAnodeQ.Fill(qAnode);
    hCathodeQ.Fill(qCathode);
    hCathodeTopQ.Fill(qCathodeTop);
    anodeCharges.push_back(qAnode);
    cathodeCharges.push_back(qCathode);
    cathodeTopCharges.push_back(qCathodeTop);

    if (qAnode > 0.) {
      const double ratio = qCathode / qAnode;
      hRatio.Fill(ratio);
      chargeRatios.push_back(ratio);
    }

    if (ev == 0) {
      const double dt =
          std::chrono::duration<double>(std::chrono::steady_clock::now() - tEvent).count();
      std::cout << "  [timing] first event: " << FormatNumber(dt, 2) << " s"
                << " (" << ne << " e⁻ tracked)\n";
    }

    if ((ev + 1) % progressStep == 0 || ev + 1 == sim.nEvents) {
      std::cout << "  height=" << distLabel << ": "
                << (ev + 1) << "/" << sim.nEvents << " events processed\n";
    }
  }

  // Primary-electron fate summary (diagnostic): multiply fraction + where/why each
  // primary ended, so a run that "shows no avalanche" can be read as collection loss
  // (on-plate), attachment, or something anomalous (e.g. outside time window).
  std::cout << "  [fate] multiplied " << nMultiplied << "/" << sim.nEvents
            << " events; primary endpoint:";
  for (const auto& [label, cnt] : primaryFate) {
    std::cout << " {" << label << ": " << cnt << "}";
  }
  std::cout << "\n";

  // ── Write histograms ─────────────────────────────────────────────────────────
  if (distDir) {
    distDir->cd();
    hAnodeQ.Write("h_anode_charge");
    hCathodeQ.Write("h_cathode_charge");
    hCathodeTopQ.Write("h_cathode_top_charge");
    hRatio.Write("h_ratio_charge");
    hNprimary.Write("h_n_primary_electrons");
    hAvalSize.Write("h_avalanche_size");
    pAnodeSignal.Write("p_anode_signal");
    pCathodeSignal.Write("p_cathode_signal");
    pCathodeTopSignal.Write("p_cathode_top_signal");
    pAnodeElec.Write("p_anode_electron");
    pAnodeIon.Write("p_anode_ion");
    pCathodeElec.Write("p_cathode_electron");
    pCathodeIon.Write("p_cathode_ion");
    pAnodeAmp.Write("p_anode_amp");
    pCathodeAmp.Write("p_cathode_amp");
    pAnodeAmpInt.Write("p_anode_amp_int");
    pCathodeAmpInt.Write("p_cathode_amp_int");
    signalTree.Write("t_signals");
  }

  // ── Build summary ─────────────────────────────────────────────────────────────
  DistanceSummary s;
  s.distanceMm          = distOptMm;
  s.nEvents             = sim.nEvents;
  s.nInteracted         = nInteracted;
  s.interactionFraction = sim.nEvents > 0
                              ? static_cast<double>(nInteracted) / static_cast<double>(sim.nEvents)
                              : 0.;
  s.meanAnodeChargeFC   = Mean(anodeCharges);
  s.rmsAnodeChargeFC    = Rms(anodeCharges, s.meanAnodeChargeFC);
  s.semAnodeChargeFC    = Sem(s.rmsAnodeChargeFC, anodeCharges.size());
  s.meanCathodeChargeFC = Mean(cathodeCharges);
  s.rmsCathodeChargeFC  = Rms(cathodeCharges, s.meanCathodeChargeFC);
  s.semCathodeChargeFC  = Sem(s.rmsCathodeChargeFC, cathodeCharges.size());
  s.meanCathodeTopChargeFC = Mean(cathodeTopCharges);
  s.rmsCathodeTopChargeFC  = Rms(cathodeTopCharges, s.meanCathodeTopChargeFC);
  s.semCathodeTopChargeFC  = Sem(s.rmsCathodeTopChargeFC, cathodeTopCharges.size());
  s.meanChargeRatio     = Mean(chargeRatios);
  s.rmsChargeRatio      = Rms(chargeRatios, s.meanChargeRatio);
  s.semChargeRatio      = Sem(s.rmsChargeRatio, chargeRatios.size());
  s.meanPrimaryElectrons = Mean(primaryCounts);
  s.meanAvalancheSize    = Mean(avalancheSizes);
  return s;
}

// ─── Summary graphs ───────────────────────────────────────────────────────────

void WriteSummaryGraphs(const std::vector<DistanceSummary>& sums,
                        TDirectory* summaryDir, const fs::path& pngPath) {
  if (sums.empty()) return;
  const std::size_t n = sums.size();
  std::vector<double> x(n), xe(n, 0.);
  std::vector<double> qa(n), qaE(n), qc(n), qcE(n), rat(n), ratE(n), gain(n), gainE(n, 0.);

  for (std::size_t i = 0; i < n; ++i) {
    x[i]    = sums[i].distanceMm.value_or(static_cast<double>(i));
    qa[i]   = sums[i].meanAnodeChargeFC;   qaE[i]  = sums[i].semAnodeChargeFC;
    qc[i]   = sums[i].meanCathodeChargeFC; qcE[i]  = sums[i].semCathodeChargeFC;
    rat[i]  = sums[i].meanChargeRatio;     ratE[i] = sums[i].semChargeRatio;
    gain[i] = sums[i].meanAvalancheSize;
  }

  auto MakeGraph = [&](const char* name, const char* title,
                       const std::vector<double>& y, const std::vector<double>& ye,
                       int marker) {
    TGraphErrors g(static_cast<int>(n), x.data(), y.data(), xe.data(), ye.data());
    g.SetName(name);
    g.SetTitle(title);
    g.SetMarkerStyle(marker);
    g.SetLineWidth(2);
    if (summaryDir) { summaryDir->cd(); g.Write(); }
    return g;
  };

  auto gAnode   = MakeGraph("g_anode_charge",
    "Mean anode charge;Drift-gap height [mm];Q_{anode} [fC]", qa, qaE, 20);
  auto gCathode = MakeGraph("g_cathode_charge",
    "Mean cathode charge;Drift-gap height [mm];Q_{cathode} [fC]", qc, qcE, 21);
  auto gGain    = MakeGraph("g_avalanche_size",
    "Mean avalanche size;Drift-gap height [mm];N_{e,total}", gain, gainE, 22);
  auto gRatio   = MakeGraph("g_charge_ratio",
    "Charge ratio;Drift-gap height [mm];Q_{cathode}/Q_{anode}", rat, ratE, 23);

  TCanvas canvas("c_thgem_summary", "THGEM summary", 2400, 500);
  canvas.Divide(4, 1);
  canvas.cd(1); gAnode.Draw("APL");
  canvas.cd(2); gCathode.Draw("APL");
  canvas.cd(3); gGain.Draw("APL");
  canvas.cd(4); gRatio.Draw("APL");
  EnsureDirectory(pngPath.parent_path());
  canvas.SaveAs(pngPath.string().c_str());
}

// ─── CSV summary ─────────────────────────────────────────────────────────────

void WriteSummaryCsv(const fs::path& path, const std::vector<DistanceSummary>& sums) {
  std::ofstream f(path);
  if (!f) throw std::runtime_error("Cannot write CSV: " + path.string());

  f << "source_distance_mm,x_position_cm,n_events,n_interacted,interaction_fraction,"
       "mean_anode_charge_fC,rms_anode_charge_fC,sem_anode_charge_fC,"
       "mean_cathode_charge_fC,rms_cathode_charge_fC,sem_cathode_charge_fC,"
       "mean_cathode_top_charge_fC,rms_cathode_top_charge_fC,sem_cathode_top_charge_fC,"
       "mean_charge_ratio,rms_charge_ratio,sem_charge_ratio,"
       "mean_primary_electrons,mean_avalanche_size\n";

  f << std::fixed << std::setprecision(6);
  for (const auto& s : sums) {
    if (s.distanceMm) f << *s.distanceMm; else f << "random";
    f << ',';
    if (s.xPositionCm.has_value()) f << *s.xPositionCm;
    f << ','
      << s.nEvents                   << ','
      << s.nInteracted               << ','
      << s.interactionFraction       << ','
      << s.meanAnodeChargeFC         << ','
      << s.rmsAnodeChargeFC          << ','
      << s.semAnodeChargeFC          << ','
      << s.meanCathodeChargeFC       << ','
      << s.rmsCathodeChargeFC        << ','
      << s.semCathodeChargeFC        << ','
      << s.meanCathodeTopChargeFC    << ','
      << s.rmsCathodeTopChargeFC     << ','
      << s.semCathodeTopChargeFC     << ','
      << s.meanChargeRatio           << ','
      << s.rmsChargeRatio            << ','
      << s.semChargeRatio            << ','
      << s.meanPrimaryElectrons      << ','
      << s.meanAvalancheSize         << '\n';
  }
}

// ─── Config echo ──────────────────────────────────────────────────────────────

json ConfigToJson(const Config& cfg, const ThgemGeom& g) {
  json jSrc = {{"energy_keV", cfg.source.energyKeV}};
  jSrc["source_distances_mm"] = cfg.source.fixedDistMm.has_value()
                                     ? json(*cfg.source.fixedDistMm) : json(nullptr);
  jSrc["x_positions_cm"] = cfg.source.fixedXCmList.has_value()
                               ? json(*cfg.source.fixedXCmList) : json(nullptr);
  return {
    {"geometry", {
      {"hole_diameter_um",       cfg.geometry.holeDiameterUm},
      {"hole_pitch_um",          cfg.geometry.holePitchUm},
      {"plate_thickness_um",     cfg.geometry.plateThicknessUm},
      {"copper_thickness_um",    cfg.geometry.copperThicknessUm},
      {"rim_um",                 cfg.geometry.rimUm},
      {"drift_gap_mm",           cfg.geometry.driftGapMm},
      {"induction_gap_mm",       cfg.geometry.inductionGapMm},
      {"dielectric_material",    cfg.geometry.dielectric},
      {"target_element_size_um", cfg.geometry.targetElementSizeUm},
      {"min_elements",           cfg.geometry.minElements},
      {"max_elements",           cfg.geometry.maxElements},
      {"periodic_copies",        cfg.geometry.periodicCopies},
      {"hole_sectors",           cfg.geometry.holeSectors},
      {"grid_nx",                cfg.geometry.gridNx},
      {"grid_nz",                cfg.geometry.gridNz}
    }},
    {"fields", {
      {"e_drift_kvcm",     cfg.fields.eDriftKvcm},
      {"delta_v_thgem_V",  cfg.fields.deltaVThgemV},
      {"e_induction_kvcm", cfg.fields.eInductionKvcm}
    }},
    // Derived electrode potentials [V] and cell geometry [cm], echoed for the GUI.
    {"derived", {
      {"v_drift",    g.vDrift},
      {"v_top_cu",   g.vTopCu},
      {"v_bot_cu",   g.vBotCu},
      {"v_anode",    g.vAnode},
      {"z_drift_cm", g.zDrift},
      {"z_anode_cm", g.zAnode},
      {"z_top_cu_top_cm", g.zTopCuTop},
      {"z_bot_cu_bot_cm", g.zBotCuBot},
      {"z_diel_half_cm",  g.zDielHalf},
      {"r_hole_cm",  g.rHoleCm},
      {"pitch_cm",   g.pitchCm}
    }},
    {"source", jSrc},
    {"gas", {
      {"gas1",                   cfg.gas.gas1},
      {"gas1_fraction_pct",      cfg.gas.frac1},
      {"gas2",                   cfg.gas.gas2},
      {"ion_species",            cfg.gas.ionSpecies},
      {"temperature_K",          cfg.gas.temperatureK},
      {"pressure_Torr",          cfg.gas.pressureTorr},
      {"enable_penning",         cfg.gas.enablePenning},
      {"n_magboltz_collisions",  cfg.gas.nCollisions},
      {"max_electron_energy_eV", cfg.gas.maxElectronEnergyEV},
      {"transport_max_energy_eV", cfg.gas.transportMaxEnergyEV},
      {"n_field_points",         cfg.gas.nFieldPoints},
      {"e_field_min_vcm",        cfg.gas.eFieldMinVcm},
      {"e_field_max_vcm",        cfg.gas.eFieldMaxVcm},
      {"w_value_eV",             cfg.gas.wValueEV}
    }},
    {"simulation", {
      {"n_events",           cfg.simulation.nEvents},
      {"max_avalanche_size", cfg.simulation.maxAvalancheSize},
      {"time_window_ns",     cfg.simulation.timeWindowNs},
      {"time_step_ns",       cfg.simulation.timeStepNs},
      {"enable_ion_drift",   cfg.simulation.enableIonDrift},
      {"store_drift_lines",  cfg.simulation.storeDriftLines},
      {"ion_max_step_um",    cfg.simulation.ionMaxStepUm},
      {"ion_time_window_ns", cfg.simulation.ionTimeWindowNs},
      {"max_ions_drifted",   cfg.simulation.maxIonsDrifted},
      {"random_seed",        cfg.simulation.randomSeed}
    }}
  };
}

std::string BuildRunFolderName(const Config& cfg) {
  std::time_t now = std::time(nullptr);
  std::tm tm_local = *std::localtime(&now);
  std::ostringstream ss;
  ss << std::put_time(&tm_local, "%y%m%d_%H-%M__")
     << "dV" << static_cast<int>(cfg.fields.deltaVThgemV)
     << "V__n" << cfg.simulation.nEvents;
  return ss.str();
}

} // namespace

// ─── main ─────────────────────────────────────────────────────────────────────

int main(int argc, char* argv[]) {
  try {
    std::cout << std::unitbuf;   // stream the log to the GUI in real time

    gROOT->SetBatch(true);
    gStyle->SetOptStat(1110);
    TH1::AddDirectory(false);
    TH1::StatOverflows(true);
    const auto opts = ParseCli(argc, argv);
    Config cfg = LoadConfig(opts.configPath);

    const auto seed = static_cast<UInt_t>(cfg.simulation.randomSeed);
    gRandom->SetSeed(seed);
    Garfield::RandomEngineRoot rngEngine;
    rngEngine.SetSeed(seed);
    Garfield::Random::SetEngine(rngEngine);

    if (opts.singleDistanceMm)
      cfg.source.fixedDistMm = std::vector<double>{*opts.singleDistanceMm};

    const fs::path runDir = opts.outDir /
        (opts.runName.empty() ? BuildRunFolderName(cfg) : opts.runName);
    EnsureDirectory(runDir);

    std::cout << "THGEM Garfield++ simulation\n"
              << "  config  : " << opts.configPath << "\n"
              << "  output  : " << runDir << "\n"
              << "  geometry: hole " << cfg.geometry.holeDiameterUm << " µm dia, "
              << cfg.geometry.holePitchUm << " µm pitch, plate "
              << cfg.geometry.plateThicknessUm << " µm "
              << cfg.geometry.dielectric << " + 2×"
              << cfg.geometry.copperThicknessUm << " µm Cu\n"
              << "  gaps    : drift " << cfg.geometry.driftGapMm << " mm, induction "
              << cfg.geometry.inductionGapMm << " mm\n"
              << "  fields  : ΔV_THGEM " << cfg.fields.deltaVThgemV << " V, E_drift "
              << cfg.fields.eDriftKvcm << " kV/cm, E_ind "
              << cfg.fields.eInductionKvcm << " kV/cm\n"
              << "  gas     : " << cfg.gas.gas1 << ":" << cfg.gas.gas2 << " "
              << static_cast<int>(cfg.gas.frac1) << ":"
              << static_cast<int>(100. - cfg.gas.frac1) << ", "
              << cfg.gas.temperatureK << " K, " << cfg.gas.pressureTorr << " Torr\n"
              << "  source  : " << cfg.source.energyKeV << " keV, "
              << (cfg.source.fixedDistMm.has_value()
                    ? std::to_string(cfg.source.fixedDistMm->size()) + " height point(s)"
                    : "random height")
              << "\n  events  : " << cfg.simulation.nEvents << " per point\n";

    using Clock = std::chrono::steady_clock;
    auto secsSince = [](Clock::time_point t0) {
      return std::chrono::duration<double>(Clock::now() - t0).count();
    };

    // Gas (shared across all height points).
    std::cout << "\nSetting up gas...\n";
    auto tGas = Clock::now();
    MediumMagboltz gas(cfg.gas.gas1, cfg.gas.frac1,
                       cfg.gas.gas2, 100. - cfg.gas.frac1);
    SetupGas(gas, cfg.gas, cfg.simulation.enableIonDrift);
    std::cout << "  [timing] gas setup: " << FormatNumber(secsSince(tGas), 1) << " s\n";

    // THGEM cell + transport field.  neBEM solves the real field; it is sampled
    // once onto a ComponentGrid (fast trilinear interpolation during the
    // avalanche — direct neBEM lookups are ~10³× too slow) and cached by
    // geometry/fields so repeat runs skip the solve entirely.
    ThgemDetector detector(cfg.geometry, cfg.fields, gas);
    const ThgemGeom& g = detector.Geom();
    std::cout << "\n  Electrode potentials: V_drift=" << g.vDrift
              << " V, V_topCu=" << g.vTopCu << " V, V_botCu=" << g.vBotCu
              << " V, V_anode=" << g.vAnode << " V\n";

    ComponentGrid grid;
    const double gxy = kGridHalfSpanFactor * g.pitchCm;
    grid.SetMesh(static_cast<std::size_t>(cfg.geometry.gridNx),
                 static_cast<std::size_t>(cfg.geometry.gridNx),
                 static_cast<std::size_t>(cfg.geometry.gridNz),
                 -gxy, gxy, -gxy, gxy, g.zAnode, g.zDrift);
    // One-cell mesh tiled with mirror periodicity → sideways diffusion wraps
    // into neighbouring cells (charges are collected only in z, at the anode /
    // drift cathode), just like the periodic Garfield GEM field maps.
    grid.EnableMirrorPeriodicityX();
    grid.EnableMirrorPeriodicityY();

    // Sampled neBEM field caches live in field_cache/ (generated; gitignored).
    EnsureDirectory("field_cache");
    const std::string fieldCache =
        (fs::path("field_cache") / DeriveFieldCacheName(cfg.geometry, cfg.fields)).string();
    const std::size_t expectNodes = static_cast<std::size_t>(cfg.geometry.gridNx) *
                                    cfg.geometry.gridNx * cfg.geometry.gridNz;
    auto tField = Clock::now();
    bool haveField = false;
    if (fs::exists(fieldCache)) {
      std::cout << "\nLoading cached transport field from: " << fieldCache << "\n";
      const std::size_t nLines = CountFileLines(fieldCache);
      if (nLines == expectNodes &&
          grid.LoadElectricField(fieldCache, "xyz",
                                 /*withPotential=*/true, /*withFlag=*/true)) {
        haveField = true;
      } else {
        std::cout << "  Cached field is incomplete or unreadable (" << nLines << "/"
                  << expectNodes << " nodes) — deleting and regenerating.\n";
        std::error_code ec;
        fs::remove(fieldCache, ec);
      }
    }
    if (!haveField) {
      std::cout << "\nSolving THGEM field with neBEM and sampling the "
                << cfg.geometry.gridNx << "×" << cfg.geometry.gridNx << "×"
                << cfg.geometry.gridNz << " transport grid"
                << " (one-time; cached to " << fieldCache << ")...\n";
      if (!detector.Initialise())
        throw std::runtime_error("neBEM Initialise() failed — try a coarser mesh "
                                 "(larger target_element_size_um / fewer periodic_copies).");
      std::cout << "  neBEM solved (" << detector.Component().GetNumberOfElements()
                << " boundary elements). Sampling transport grid (be patient)...\n";
      SampleFieldToFile(detector.Component(), detector, g, cfg.geometry, gxy, fieldCache);
      if (!grid.LoadElectricField(fieldCache, "xyz",
                                  /*withPotential=*/true, /*withFlag=*/true))
        throw std::runtime_error("Failed to load freshly sampled transport field: "
                                 + fieldCache);
    }
    grid.SetMedium(&gas);   // must follow SetMesh(): SetMesh() calls Reset().
    std::cout << "  [timing] transport field: "
              << FormatNumber(secsSince(tField), 1) << " s\n";

    // Analytic anode weighting field (parallel-plate induction-gap model).
    ComponentUser wAnode;
    SetupAnodeWeighting(wAnode, g);

    Sensor sensor;
    SetupSensor(sensor, grid, wAnode, g, cfg.simulation);

    // ROOT output.
    TFile rootFile((runDir / "thgem_sim.root").string().c_str(), "RECREATE");
    if (rootFile.IsZombie())
      throw std::runtime_error("Failed to create ROOT file in " + runDir.string());

    TDirectory* summaryDir = rootFile.mkdir("summary");
    TDirectory* fieldDir   = rootFile.mkdir("field");
    auto tDump = Clock::now();
    DumpFieldMap(grid, g, fieldDir);
    std::cout << "  [timing] field-map dump: " << FormatNumber(secsSince(tDump), 1) << " s\n";

    std::vector<DistanceSummary> allSummaries;

    std::vector<std::optional<double>> dList;
    if (cfg.source.fixedDistMm.has_value() && !cfg.source.fixedDistMm->empty()) {
      for (double d : *cfg.source.fixedDistMm) dList.push_back(d);
    } else {
      dList.push_back(std::nullopt);
    }
    std::vector<std::optional<double>> xList;
    if (cfg.source.fixedXCmList.has_value() && !cfg.source.fixedXCmList->empty()) {
      for (double x : *cfg.source.fixedXCmList) xList.push_back(x);
    } else {
      xList.push_back(std::nullopt);
    }

    for (const auto& dOpt : dList) {
      for (const auto& xOpt : xList) {
        std::string label = dOpt.has_value() ? FormatNumber(*dOpt) + " mm" : "random";
        if (xOpt.has_value()) label += "  x=" + FormatNumber(*xOpt * 10.0) + " mm";
        std::cout << "\n--- Drift-gap height: " << label << " ---\n";

        std::string tag = dOpt.has_value()
            ? "dist_" + FileSafeNumber(*dOpt) + "mm" : "dist_rnd";
        if (xOpt.has_value())
          tag += "_x" + FileSafeNumber(*xOpt * 10.0) + "mm";
        TDirectory* distDir = rootFile.mkdir(tag.c_str());
        if (!distDir) throw std::runtime_error("Failed to create ROOT dir: " + tag);

        DistanceSummary summary = RunDistancePoint(cfg, g, dOpt, sensor, distDir, xOpt);
        summary.xPositionCm = xOpt;
        allSummaries.push_back(summary);

        std::cout << "  ⟨Q_anode⟩     = " << FormatNumber(summary.meanAnodeChargeFC)   << " fC"
                  << "  ±" << FormatNumber(summary.semAnodeChargeFC) << " (SEM)\n"
                  << "  ⟨Q_cathode⟩   = " << FormatNumber(summary.meanCathodeChargeFC) << " fC"
                  << "  ±" << FormatNumber(summary.semCathodeChargeFC) << " (SEM)\n"
                  << "  ⟨avalanche size⟩ = "
                  << FormatNumber(summary.meanAvalancheSize, 0) << " electrons\n";
      }
    }

    WriteSummaryGraphs(allSummaries, summaryDir, runDir / "summary" / "thgem_summary.png");
    rootFile.Write();
    rootFile.Close();

    WriteSummaryCsv(runDir / "summary.csv", allSummaries);
    WriteJsonFile(runDir / "run_config.json", ConfigToJson(cfg, g));

    std::cout << "\nDone. Results written to " << runDir << "\n";
    return 0;

  } catch (const std::exception& e) {
    std::cerr << "Error: " << e.what() << "\n";
    return 1;
  }
}
