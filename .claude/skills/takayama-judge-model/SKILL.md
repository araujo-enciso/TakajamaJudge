---
name: takayama-judge-model
description: Builds and solves Takayama-Judge spatial price equilibrium (allocation) models in GAMS or in Python/Pyomo (the user chooses) - regions with linear supply and demand, transport costs between them - and reports equilibrium prices, quantities and trade flows. Use when the user asks for a Takayama-Judge model, a spatial price equilibrium, or an allocation/trade-flow model between regions.
---

# Takayama-Judge Spatial Equilibrium Model (GAMS or Pyomo)

Build a working model that finds the competitive equilibrium of a commodity
traded between regions, following Takayama and Judge's quadratic programming
formulation. The model can be written in **GAMS** or in **Python with Pyomo**;
the user chooses (Step 0). Always start from the matching template in this
skill folder and adapt it to the user's data:

| Language | Deterministic model | Model with random shocks |
|---|---|---|
| GAMS | `tj_template.gms` | `tj_noise_template.gms` |
| Pyomo (Python) | `tj_template.py` | `tj_noise_template.py` |

The economics, interview, scenarios, checks and reports are the same in both
languages; only the code and the output files differ (sections 2-6).

## 1. Interview the user for the inputs

Do not write any code until all inputs are collected and confirmed. Ask in
plain, non-technical language, **one step at a time**, and wait for the answer
before moving on. Accept answers in any form (typed values, a pasted table,
or a CSV/Excel file in the workspace). Ask in the user's language.

**Step 0 - Modelling language.** Always ask first: "Do you want the model in
GAMS or in Python (Pyomo)?" Explain the difference in one or two sentences:
- *GAMS*: the classic algebraic modelling language; needs a GAMS installation
  and licence; outputs `.lst`, `.gdx` and an Excel workbook.
- *Pyomo*: free and open source, runs in Python
  (`pip install pyomo highspy pandas numpy openpyxl matplotlib`); outputs a
  `.py` script, a run log and an Excel workbook.
There is no default: wait for the user's choice. If the user chooses GAMS,
check whether `gams` is available; if they choose Pyomo, check that Python,
Pyomo and a QP solver (HiGHS by default) are installed. If the required
software is missing, say so and offer to install it (Pyomo) or ask the user to
install it (GAMS) before running.

**Step 1 - Commodity and units.** Ask what product is traded, the quantity
unit (e.g. thousand tonnes) and the currency.

**Step 2 - Regions.** Ask how many regions and their names. For each region,
ask whether it produces, consumes, or both.

**Step 3 - Demand (for each consuming region).** Offer two ways to answer:
- (a) a base price, base quantity and price elasticity of demand, or
- (b) the linear coefficients of `price = a - b * quantity`.
Most users find (a) easier; suggest it first.

**Step 4 - Supply (for each producing region).** Same two options:
- (a) base price, base quantity and supply elasticity, or
- (b) coefficients of `price = c + d * quantity`.

**Step 5 - Transport costs.** Ask for the cost of moving one unit between
each pair of regions. Offer a ready-to-fill table with the region names as
rows and columns, and 0 on the diagonal. Ask whether costs are the same in
both directions (then fill one half only).

**Step 6 - Policies and scenarios.** Ask whether to include route capacity
limits, tariffs, subsidies, or fixed supply/demand in any region. In addition
to the base case, every model must include at least one alternative scenario
and report a comparison. Ask which parameter or policy changes and its value
in the alternative; never invent the scenario or its data. If the user has not
chosen a scenario, offer clear examples based on their model (such as a
different tariff rate) and wait for them to select or define one. Confirm that
the base case and alternative scenario differ only in the specified inputs.
Policies and scenarios are limited to ad-valorem tariffs on trade routes and
export subsidies. Ad-valorem tariffs are implemented as a percentage of the
trade price, and subsidies as a percentage of the trade price paid to the
exporter. The policy scenario is solved as a sequence of convex quadratic
programs: each solve keeps the policy wedge fixed, the wedge for the next
iteration is calculated from the previous solve's prices, and the process
repeats until the prices converge to a stable equilibrium in which the market
clears and all constraints are satisfied. The results are compared to the
base case.

**Step 7 - Random shocks (noise).** Always ask: "Do you want random shocks
in the model, so prices and quantities change over time?" Default: no.
If yes, ask in this order:
1. **Number of periods** (e.g. 500).
2. **Where the shock goes**: the supply intercept (default, as in the
   classic version), the demand intercept, or both; and in which regions.
3. **Type of shock**:
   - *White noise*: a new independent shock each period, `e(i,t) ~ N(0, sigma)`.
   - *Random walk*: shocks accumulate over time, `u(i,t) = u(i,t-1) + e(i,t)`,
     so the intercept drifts. Explain the difference in one sentence.
4. **Size of the shock**: standard deviation `sigma` (default 1, in price units).
5. **Seed**: fixed (same random numbers every run, reproducible - default) or
   new random numbers each run (GAMS `execseed = gmillisec(jnow)`; Python a
   seed taken from the clock).
If yes, build from the noise template of the chosen language (section 5).

**Step 8 - Confirm.** Show all inputs back in tables (language, regions,
demand, supply, transport costs, shock settings, and each scenario's changed
inputs) with any converted coefficients, and ask the user to confirm or
correct them. Ask for the model name and use it to create
`models/<model-name>/`. Only then build the model.

Rules:
- Never invent data. If the user just wants to try the agent, offer the
  illustrative data in the template and say clearly that it is made up.
- Check values as they come in: slopes and elasticities must be positive,
  prices and quantities non-negative, the cost table complete. Ask again if not.
- Converting elasticities to linear coefficients (show the result):
  demand `b = P0 / (|e_d| * Q0)`, `a = P0 + b*Q0`;
  supply `d = P0 / (e_s * Q0)`, `c = P0 - d*Q0`.

## 2. Model structure (both languages)

Every model must solve a base case and at least one user-confirmed alternative
scenario. Add a scenario set and index scenario-specific results by it. Keep
shared data and random shock draws common across cases; change only the inputs
the user assigned to each scenario. Do not copy scenario-specific values into
the shared base parameters or silently assume that a scenario has no effect.

Always use the Takayama-Judge quadratic-programming formulation for
equilibrium solves. Do not solve policy scenarios as MCPs (or as any
complementarity/equation-system solve in Python). Fix the policy wedge during
each QP solve, then update it outside the QP from the previous solve's price
duals. For ad-valorem tariffs use `w(i,j) = phi(i,j) * P_dem(j)`; for export
subsidies use `w(i,j) = -sig(i,j) * P_sup(i)`; when both apply,
`w(i,j) = phi(i,j)*P_dem(j) - sig(i,j)*P_sup(i)`. Iterate: solve the QP,
calculate the target wedge, and update the wedge until the maximum wedge
change is below a documented tolerance. Use damping when needed, set a
maximum iteration count, and stop with a clear error if the iteration does
not converge. After convergence, solve once more with the final wedge and
check the policy-adjusted arbitrage conditions. Every individual solve must
remain a QP solve.

Variables (non-negative):
- `x(i)` quantity supplied in region i
- `y(j)` quantity consumed in region j
- `q(i,j)` quantity shipped from i to j

Objective - maximize Net Social Payoff (with the policy wedge `w`):

    NSP = sum(j, a(j)*y(j) - 0.5*b(j)*y(j)^2)
        - sum(i, c(i)*x(i) + 0.5*d(i)*x(i)^2)
        - sum((i,j), t(i,j)*q(i,j))
        - sum((i,j) with i<>j, w(i,j)*q(i,j))

Constraints:
- `dembal(j)`: `y(j) <= sum(i, q(i,j))`
- `supbal(i)`: `sum(j, q(i,j)) <= x(i)`
- Optional route capacity: upper bound `cap(i,j)` on `q(i,j)`.

Prices are the constraint duals (shadow prices):
- `P_dem(j)` = dual of `dembal(j)` = demand price in region j
- `P_sup(i)` = dual of `supbal(i)` = supply price in region i

### 2a. GAMS specifics

- Keep the standard GAMS block order, each block commented:
  `Sets` -> `Alias` -> `Parameters` / `Table` -> `Variables` -> `Equations`
  (declaration, then definition) -> `Model` -> `Solve` -> reporting.
- Declare `x`, `y`, `q` as `Positive Variables` and `nsp` as a free variable
  defined by the equation `obj.. nsp =e= ...`.
- Solve with `solve tj using qcp maximizing nsp;` for each fixed wedge.
- Prices: `dembal.m(j)` and `supbal.m(i)`. Wedge update:
  `w(i,j) = phi(i,j)*dembal.m(j) - sig(i,j)*supbal.m(i)`.
- Route capacity: `q.up(i,j) = cap(i,j);`
- Validation failures: `abort` with a clear message.

### 2b. Pyomo specifics

Follow the structure of `tj_template.py`:
- Keep the same block order as comments: sets -> data -> scenarios ->
  `build_model()` (Set, Param, Var, Objective, Constraint) -> solve ->
  checks -> reporting.
- Data as Python dicts passed to `pyo.Param`; regions as one `pyo.Set`
  (no alias needed: loop over the same set twice).
- Variables: `pyo.Var(..., within=pyo.NonNegativeReals)`. The objective is
  `pyo.Objective(expr=..., sense=pyo.maximize)` (no `nsp` variable).
- Anything that changes between solves (the wedge `w`, shocked intercepts)
  must be a `pyo.Param(..., mutable=True)` so the model is built once and
  only the values are updated.
- Prices: declare `m.dual = pyo.Suffix(direction=pyo.Suffix.IMPORT)` and read
  `m.dual[m.dembal[j]]`, `m.dual[m.supbal[i]]`. Dual signs for maximisation
  differ between solvers, so report them as positive prices
  (`abs(...)`) and document this in the code.
- Solver: `pyo.SolverFactory("highs")` (HiGHS via `highspy`). Do not use
  `appsi_highs`: it rejects quadratic objectives. Gurobi, CPLEX or Ipopt can
  be used instead if the user has them; only the solver name changes.
- Check `res.solver.termination_condition == pyo.TerminationCondition.optimal`
  after every solve.
- Route capacity: `m.q[i, j].setub(cap[i, j])`.
- Validation failures: `raise RuntimeError(...)` with a clear message.
- Random numbers: `numpy.random.default_rng(seed)`; random walk with
  `np.cumsum`. Note to the user that draws differ from GAMS's `normal()` even
  with the same seed, so results are statistically, not numerically, equal.

## 3. Validate the equilibrium

The script must check, and stop (`abort` in GAMS, `raise` in Python) with a
clear message if a check fails, for every scenario (and every period):
1. Solver status is optimal (GAMS `tj.modelstat` = 1 or 2; Pyomo
   termination condition `optimal`).
2. No arbitrage: `P_dem(j) - P_sup(i) - t(i,j) - w(i,j) <= 1e-4`
   for every route.
3. Active routes: where `q(i,j) > 1e-6`, price difference equals
   `t(i,j) + w(i,j)`.
4. Marginal prices match the curves: `P_dem(j) = a(j) - b(j)*y(j)`
   where `y(j) > 0`.

If a check fails, explain why and fix the model before reporting.

## 4. Report the results

Build these result tables, indexed by scenario (and period when there are
shocks), as plain tables (no dashboards):
- **regional(r,\*)**: supply, demand, demand price, supply price, net exports.
- **flows(i,j)**: only non-zero shipments.
- **welfare(\*)**: consumer surplus `sum 0.5*b*y^2`, producer surplus
  `sum 0.5*d*x^2`, transport cost, policy wedge revenue/cost, total NSP.

Always save model outputs in the model's own folder `models/<model-name>/`.

### 4a. GAMS outputs

Each completed run must create:
- `tj_model.gms`: runnable model source with all input data and scenario
  definitions at the top.
- `tj_model.lst`: GAMS listing from the actual completed run, including
  validation results and a short plain-language summary of the comparison.
- `tj_results.gdx`: model inputs and solved variables/results for every
  scenario and period.
- `tj_results.xlsx`: one workbook created by `gdxxrw` from `tj_results.gdx`,
  with scenario- and time-indexed prices, supply, demand, shocks, trade
  flows, welfare, price summaries, and the input parameters on separate
  worksheets.

Keep the GAMS reporting/export section simple: create report parameters with
the scenario, time, and region dimensions, unload them once to GDX, and use
`gdxxrw` to write the symbols to the workbook. Do not write CSV files or use
GAMS `put` statements or explicit GAMS loops to format or export rows. Use a
small `gdxxrw` command file to map symbols to workbook sheets when needed.
When a graphic is requested, put its complete Python plotting implementation
inside the `.gms` source using GAMS execution-time embedded code:
`embeddedCode Python:` ... `endEmbeddedCode`. Read the solved symbols directly
through `gams.get(...)`; do not create or depend on a separate plotting script
or intermediate CSV files. Write the requested graphic (for example
`scenario_comparison.svg`) beside the model and check that it was created.

Run with `gams tj_model.gms` inside the model folder.

### 4b. Pyomo outputs

Each completed run must create:
- `tj_model.py`: runnable script with all input data and scenario
  definitions at the top (same layout as `tj_template.py`).
- `tj_model.log`: console output of the actual completed run
  (`python tj_model.py > tj_model.log 2>&1`), including solver status,
  wedge-iteration counts, validation results, the result tables and a short
  plain-language summary of the comparison (the equivalent of the `.lst`).
- `tj_results.xlsx`: one workbook written with `pandas.ExcelWriter`, with
  scenario- and time-indexed prices, supply, demand, shocks, trade flows,
  welfare, price summaries, and the input parameters on separate worksheets.

Build the result tables as pandas DataFrames (long format with scenario /
period / region columns, pivoted to time-series tables with periods as rows
where useful) and write them once to the workbook. Do not write per-table CSV
files. When a graphic is requested, draw it with matplotlib inside
`tj_model.py` from the result DataFrames (no separate plotting script), save
it beside the model (for example `scenario_comparison.svg`) and check that it
was created.

After running (either language), summarise in 2-4 sentences: which regions
export, where prices are highest, and why.

## 5. Stochastic version with random shocks

Use when the user answered yes in Step 7. Start from `tj_noise_template.gms`
(GAMS) or `tj_noise_template.py` (Pyomo).

Common to both:
- Add a time set `t` (one market equilibrium per period, no storage).
  Transport costs are named `tc(i,j)` in this version so they don't clash
  with the time set.
- Set the switches at the top: `useNoise`, `noiseType` (1 white noise,
  2 random walk), `sigma`, `fixedSeed`, and the seed value.
- Shocks: `e(r,t) ~ N(0, sigma)`; for a random walk,
  `u(r,t) = u(r,t-1) + e(r,t)`; for white noise, `u = e`.
- Shifted intercepts: supply `ct(i,t) = c(i) + u(i,t)`; for demand shocks
  use a separate draw and `at(j,t) = a(j) + u_d(j,t)`. Use a region filter
  if only some regions are shocked.
- Use identical generated shock draws for every policy scenario.
- Run the same equilibrium checks for every period.
- Warn the user if a shifted intercept becomes negative, especially with a
  random walk over many periods.
- Report time-series tables (rows = periods): price by region, supply,
  demand, and the shock itself; plus a summary table with mean, standard
  deviation, min and max price per region and scenario.

GAMS: index every variable and equation by `t` and sum the objective over
`t` in one QCP; save the scenario/time-indexed parameters with
`execute_unload` and export with `gdxxrw`.

Pyomo: because periods are independent (no storage), build a one-period
model with the shocked intercepts as mutable Params and solve it period by
period (and scenario by scenario), as in `tj_noise_template.py`. This gives
the same equilibrium as one stacked QP, is fast, and avoids HiGHS failing on
very large QPs (it can wrongly report "non-convex" with several hundred
periods). Collect one record per (scenario, period, region) and pivot to the
time-series tables before writing the workbook.

## 6. Extensions (only when asked)

- **Multiple commodities**: add a set `k` and index every variable,
  parameter and equation by it.
- **Temporal model**: add a time set `tt`, storage variables and a storage
  cost between periods (Takayama-Judge spatial-temporal version). Periods
  are then linked, so in Pyomo solve all periods in one model (consider a
  stronger QP solver than HiGHS for many periods).
- **Policy scenarios**: tariffs or subsidies - solve the confirmed base case
  and at least one user-defined alternative in the same file using the
  iterated-QP wedge procedure above. Do not switch to MCP for ad-valorem
  policies. Make the scenario comparison standard in every model.

## Deliverables

- Ask for the language (GAMS or Pyomo) and a model name; save all
  deliverables under `models/<model-name>/`.
- GAMS: `tj_model.gms`, `tj_model.lst`, `tj_results.gdx`, `tj_results.xlsx`
  (via `gdxxrw`), all created and verified.
- Pyomo: `tj_model.py`, `tj_model.log`, `tj_results.xlsx`
  (via `pandas.ExcelWriter`), all created and verified.
- No per-table CSV files. Plots, when requested, are generated inside the
  model file (GAMS embedded Python, or matplotlib in `tj_model.py`).
- The result tables (from the `.lst` or `.log`) summarised in the chat.
- Short instructions on how to change the data and rerun.
- For stochastic models, also report a summary table with mean, standard
  deviation, minimum, and maximum price per region and scenario.
- Add comments explaining model blocks and equations, and include a short,
  plain-language comparison summary at the end of the `.lst` / `.log`.
