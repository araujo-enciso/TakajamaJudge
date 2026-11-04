"""
Takayama-Judge Spatial Price Equilibrium - Pyomo translation of tj_template.gms
-----------------------------------------------------------------------------
Single commodity, linear demand and supply, unit transport costs.
The data below is ILLUSTRATIVE - replace it with the user's data.

Adds the base vs. policy-scenario comparison required by the skill:
ad-valorem tariffs (phi) and export subsidies (sig) enter as a fixed wedge
w(i,j) in each QP solve, updated outside the QP from the price duals until
it converges (iterated-QP, never MCP).

Requires:  pip install pyomo highspy pandas openpyxl
"""
import pandas as pd
import pyomo.environ as pyo

# --- Sets (GAMS: Set r / Alias (r,i,j)) ---------------------------------
R = ["north", "centre", "south"]

# --- Data (GAMS: Parameters / Table) ------------------------------------
# Inverse demand: price = a - b*quantity ; inverse supply: price = c + d*quantity
a = {"north": 100, "centre": 120, "south": 90}
b = {"north": 1.0, "centre": 1.5, "south": 0.8}
c = {"north": 20, "centre": 40, "south": 30}
d = {"north": 0.5, "centre": 1.0, "south": 0.7}
t = {  # unit transport cost from i to j
    ("north", "north"): 0, ("north", "centre"): 5, ("north", "south"): 9,
    ("centre", "north"): 5, ("centre", "centre"): 0, ("centre", "south"): 6,
    ("south", "north"): 9, ("south", "centre"): 6, ("south", "south"): 0,
}

# --- Scenarios: only the policy inputs differ ---------------------------
# phi = ad-valorem tariff on route (share of importer price)
# sig = export subsidy on route (share of exporter price)
SCENARIOS = {
    "base":   {"phi": {}, "sig": {}},
    "tariff": {"phi": {("north", "centre"): 0.10}, "sig": {}},  # ILLUSTRATIVE
}

TOL, MAXIT, DAMP = 1e-6, 200, 0.5
SOLVER = pyo.SolverFactory("highs")  # any QP solver with duals works (gurobi, cplex, ipopt)


def build_model():
    """Model block order mirrors GAMS: sets -> params -> vars -> equations -> model."""
    m = pyo.ConcreteModel("tj")
    m.r = pyo.Set(initialize=R)                       # i and j are just m.r again

    m.a = pyo.Param(m.r, initialize=a)
    m.b = pyo.Param(m.r, initialize=b)
    m.c = pyo.Param(m.r, initialize=c)
    m.d = pyo.Param(m.r, initialize=d)
    m.t = pyo.Param(m.r, m.r, initialize=t)
    # Wedge is mutable so it can be updated between solves without rebuilding
    m.w = pyo.Param(m.r, m.r, initialize=0.0, mutable=True)

    # Positive Variables
    m.x = pyo.Var(m.r, within=pyo.NonNegativeReals)        # supply in i
    m.y = pyo.Var(m.r, within=pyo.NonNegativeReals)        # demand in j
    m.q = pyo.Var(m.r, m.r, within=pyo.NonNegativeReals)   # shipment i -> j

    # obj..  nsp =e= ...   (in Pyomo the objective is the expression itself)
    def nsp(m):
        return (sum(m.a[j] * m.y[j] - 0.5 * m.b[j] * m.y[j] ** 2 for j in m.r)
                - sum(m.c[i] * m.x[i] + 0.5 * m.d[i] * m.x[i] ** 2 for i in m.r)
                - sum(m.t[i, j] * m.q[i, j] for i in m.r for j in m.r)
                - sum(m.w[i, j] * m.q[i, j] for i in m.r for j in m.r if i != j))
    m.nsp = pyo.Objective(rule=nsp, sense=pyo.maximize)

    # dembal(j)..  y(j) =l= sum(i, q(i,j))
    m.dembal = pyo.Constraint(m.r, rule=lambda m, j: m.y[j] <= sum(m.q[i, j] for i in m.r))
    # supbal(i)..  sum(j, q(i,j)) =l= x(i)
    m.supbal = pyo.Constraint(m.r, rule=lambda m, i: sum(m.q[i, j] for j in m.r) <= m.x[i])
    # Optional route capacity (GAMS q.up(i,j) = cap(i,j)):  m.q[i, j].setub(cap)

    # GAMS equation marginals (.m) -> dual suffix
    m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)
    return m


def price(m, con, k):
    """GAMS-style marginal: positive price. Solvers differ in dual sign convention
    for maximisation, so report the absolute value (prices are >= 0 here)."""
    return abs(m.dual.get(con[k], 0.0))


def solve_qp(m):
    res = SOLVER.solve(m, load_solutions=True)
    tc = res.solver.termination_condition
    if tc != pyo.TerminationCondition.optimal:              # GAMS: abort$(modelstat ...)
        raise RuntimeError(f"Model not solved to optimality: {tc}")


def solve_scenario(m, phi, sig):
    """Iterated QP: fix wedge -> solve -> recompute wedge from duals -> repeat."""
    for (i, j) in m.w:
        m.w[i, j] = 0.0
    for it in range(1, MAXIT + 1):
        solve_qp(m)
        max_change = 0.0
        for i in m.r:
            for j in m.r:
                if i == j:
                    continue
                target = (phi.get((i, j), 0) * price(m, m.dembal, j)
                          - sig.get((i, j), 0) * price(m, m.supbal, i))
                old = pyo.value(m.w[i, j])
                new = old + DAMP * (target - old)
                max_change = max(max_change, abs(target - old))
                m.w[i, j] = new
        if max_change < TOL:
            solve_qp(m)                                      # final solve with converged wedge
            return it
    raise RuntimeError(f"Wedge iteration did not converge in {MAXIT} iterations")


def check_equilibrium(m, tol=1e-4):
    """Same three abort checks as the GAMS template, plus the wedge."""
    for i in m.r:
        for j in m.r:
            w = pyo.value(m.w[i, j]) if i != j else 0.0
            arb = price(m, m.dembal, j) - price(m, m.supbal, i) - m.t[i, j] - w
            if arb > tol:
                raise RuntimeError(f"No-arbitrage violated on {i}->{j}: {arb:.6f}")
            if pyo.value(m.q[i, j]) > 1e-6 and abs(arb) > tol:
                raise RuntimeError(f"Active route {i}->{j} without zero margin: {arb:.6f}")
    for j in m.r:
        if pyo.value(m.y[j]) > 1e-6:
            gap = price(m, m.dembal, j) - (m.a[j] - m.b[j] * pyo.value(m.y[j]))
            if abs(gap) > tol:
                raise RuntimeError(f"Demand price off the demand curve in {j}: {gap:.6f}")


def report(m, scen):
    """GAMS display tables -> pandas DataFrames (long format, indexed by scenario)."""
    regional = pd.DataFrame({
        "supply":    {r: pyo.value(m.x[r]) for r in m.r},
        "demand":    {r: pyo.value(m.y[r]) for r in m.r},
        "dem_price": {r: price(m, m.dembal, r) for r in m.r},
        "sup_price": {r: price(m, m.supbal, r) for r in m.r},
    })
    regional["net_exp"] = regional["supply"] - regional["demand"]
    flows = pd.DataFrame([(i, j, pyo.value(m.q[i, j])) for i in m.r for j in m.r
                          if pyo.value(m.q[i, j]) > 1e-6], columns=["from", "to", "qty"])
    welfare = pd.Series({
        "consumer_surplus": sum(0.5 * m.b[j] * pyo.value(m.y[j]) ** 2 for j in m.r),
        "producer_surplus": sum(0.5 * m.d[i] * pyo.value(m.x[i]) ** 2 for i in m.r),
        "transport_cost":   sum(m.t[i, j] * pyo.value(m.q[i, j]) for i in m.r for j in m.r),
        "policy_wedge":     sum(pyo.value(m.w[i, j]) * pyo.value(m.q[i, j])
                                for i in m.r for j in m.r if i != j),
        "net_social_payoff": pyo.value(m.nsp),
    }, name="value")
    for df in (regional, flows):
        df.insert(0, "scenario", scen)
    return regional.rename_axis("region").reset_index(), flows, welfare.rename(scen)


if __name__ == "__main__":
    m = build_model()
    regional, flows, welfare = [], [], []
    for scen, pol in SCENARIOS.items():
        its = solve_scenario(m, pol["phi"], pol["sig"])
        check_equilibrium(m)
        print(f"[{scen}] converged in {its} iteration(s), checks passed")
        r_, f_, w_ = report(m, scen)
        regional.append(r_); flows.append(f_); welfare.append(w_)

    regional = pd.concat(regional); flows = pd.concat(flows); welfare = pd.concat(welfare, axis=1)
    pd.set_option("display.precision", 2)
    print("\nREGIONAL\n", regional.to_string(index=False))
    print("\nFLOWS\n", flows.to_string(index=False))
    print("\nWELFARE\n", welfare)

    # GAMS: execute_unload + gdxxrw  ->  one workbook, one sheet per table
    with pd.ExcelWriter("tj_results.xlsx") as xl:
        regional.to_excel(xl, "Regional", index=False)
        flows.to_excel(xl, "Flows", index=False)
        welfare.to_excel(xl, "Welfare")
