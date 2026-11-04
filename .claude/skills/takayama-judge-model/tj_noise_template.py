"""
Takayama-Judge model with random shocks - Pyomo translation of tj_noise_template.gms
-------------------------------------------------------------------------------------
One equilibrium per period. A random shock moves the supply intercept:
    price = ct(i,t) + d(i)*quantity
  noise_type = 1 : white noise   u(i,t) = e(i,t)
  noise_type = 2 : random walk   u(i,t) = u(i,t-1) + e(i,t)
The data below is ILLUSTRATIVE - replace it with the user's data.

Requires:  pip install pyomo highspy pandas numpy openpyxl
"""
import time
import numpy as np
import pandas as pd
import pyomo.environ as pyo

# --- Shock settings (GAMS Scalars) ---------------------------------------
USE_NOISE, NOISE_TYPE, SIGMA = 1, 2, 1.0
FIXED_SEED, SEED_VALUE = 1, 12345
seed = SEED_VALUE if FIXED_SEED else int(time.time() * 1000)   # execseed
rng = np.random.default_rng(seed)

# --- Sets ----------------------------------------------------------------
T = list(range(1, 501))
R = ["r1", "r2"]

# --- Data ----------------------------------------------------------------
a = {"r1": 20, "r2": 20}
b = {"r1": 0.1, "r2": 0.2}
c = {"r1": 5, "r2": 2.5}
d = {"r1": 1, "r2": 0.5}
tc = {("r1", "r1"): 0, ("r1", "r2"): 2, ("r2", "r1"): 2, ("r2", "r2"): 0}

# --- Random shocks: vectorised, no loops needed ---------------------------
e = USE_NOISE * rng.normal(0, SIGMA, size=(len(R), len(T)))      # e(r,t)
u = np.cumsum(e, axis=1) if NOISE_TYPE == 2 else e               # random walk = cumulative sum
ct = {(r, t): c[r] + u[k, n] for k, r in enumerate(R) for n, t in enumerate(T)}
if min(ct.values()) < 0:
    print(f"WARNING: a supply intercept is negative (min {min(ct.values()):.3f})")

# --- Model: ONE period, with the shocked intercept as a mutable Param --------
# The GAMS template stacks all periods into one QP. With no storage the periods
# are independent, so solving them one by one gives the identical equilibrium,
# is faster, and avoids HiGHS's QP solver struggling with very large models.
# (With Gurobi/CPLEX/Ipopt you could also index everything by t in one model.)
m = pyo.ConcreteModel("tjnoise")
m.r = pyo.Set(initialize=R)
m.ct = pyo.Param(m.r, initialize=c, mutable=True)       # updated each period

m.x = pyo.Var(m.r, within=pyo.NonNegativeReals)
m.y = pyo.Var(m.r, within=pyo.NonNegativeReals)
m.q = pyo.Var(m.r, m.r, within=pyo.NonNegativeReals)

m.nsp = pyo.Objective(sense=pyo.maximize, expr=
      sum(a[j] * m.y[j] - 0.5 * b[j] * m.y[j] ** 2 for j in m.r)
    - sum(m.ct[i] * m.x[i] + 0.5 * d[i] * m.x[i] ** 2 for i in m.r)
    - sum(tc[i, j] * m.q[i, j] for i in m.r for j in m.r))

m.dembal = pyo.Constraint(m.r, rule=lambda m, j: m.y[j] <= sum(m.q[i, j] for i in m.r))
m.supbal = pyo.Constraint(m.r, rule=lambda m, i: sum(m.q[i, j] for j in m.r) <= m.x[i])
m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)

opt = pyo.SolverFactory("highs")
P = lambda con, k: abs(m.dual.get(con[k], 0.0))          # GAMS .m (positive price)
TOL = 1e-4
rows = []                                                # one record per (t, region)

for t in T:
    for r in R:
        m.ct[r] = ct[r, t]
    res = opt.solve(m)
    if res.solver.termination_condition != pyo.TerminationCondition.optimal:
        raise RuntimeError(f"Period {t} not solved to optimality")

    # --- Equilibrium checks for this period (GAMS abort$ ...) ---
    for i in R:
        for j in R:
            arb = P(m.dembal, j) - P(m.supbal, i) - tc[i, j]
            if arb > TOL:
                raise RuntimeError(f"No-arbitrage violated {i}->{j}, t={t}")
            if pyo.value(m.q[i, j]) > 1e-6 and abs(arb) > TOL:
                raise RuntimeError(f"Active route without zero margin {i}->{j}, t={t}")

    for r in R:
        rows.append({"t": t, "region": r, "price": P(m.dembal, r),
                     "supply": pyo.value(m.x[r]), "demand": pyo.value(m.y[r])})
print("Equilibrium checks passed for all periods")

# --- Time-series tables (rows = periods) -----------------------------------
long = pd.DataFrame(rows)
price  = long.pivot(index="t", columns="region", values="price")
supply = long.pivot(index="t", columns="region", values="supply")
demand = long.pivot(index="t", columns="region", values="demand")
shock  = pd.DataFrame(u.T, columns=R, index=price.index)
summary = price.agg(["mean", "std", "min", "max"]).T                 # std uses n-1, as in GAMS

print("\nPRICE SUMMARY\n", summary.round(3))
print("\nPRICE (first 10 periods)\n", price.head(10).round(3))

with pd.ExcelWriter("tj_noise_results.xlsx") as xl:                  # replaces execute_unload + gdxxrw
    for name, df in [("Summary", summary), ("Price", price), ("Supply", supply),
                     ("Demand", demand), ("Shock", shock)]:
        df.to_excel(xl, name)
