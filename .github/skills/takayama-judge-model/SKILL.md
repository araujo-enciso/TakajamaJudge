---
name: takayama-judge-model
description: Builds and solves Takayama-Judge spatial price equilibrium (allocation) models in GAMS - regions with linear supply and demand, transport costs between them - and reports equilibrium prices, quantities and trade flows. Use when the user asks for a Takayama-Judge model, a spatial price equilibrium, or an allocation/trade-flow model between regions.
---

# Takayama-Judge Spatial Equilibrium Model (GAMS)

Build a working GAMS model that finds the competitive equilibrium of a
commodity traded between regions, following Takayama and Judge's quadratic
programming formulation. Start from the template `tj_template.gms` in this
skill folder and adapt it to the user's data.

## 1. Interview the user for the inputs

Do not write any code until all inputs are collected and confirmed. Ask in
plain, non-technical language, **one step at a time**, and wait for the answer
before moving on. Accept answers in any form (typed values, a pasted table,
or a CSV/Excel file in the workspace).

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
in the alternative; never invent the scenario or its data. If the user has not chosen a scenario, offer clear examples based on their model (such as a
different tariff rate) and wait for them to select or define one. Confirm that the base case and alternative scenario differ only in the specified inputs.
Policies and scenarios are limited to ad-valorem tariffs on trade routes and export subsidies.
Ad-valorem tariffs are implemented as a percentage of the trade price, and subsidies as a percentage of the trade price paid to the exporter.
The solution for the policy scenario is solved in the model as a convex quadratic program, and the results are compared to the base case.
The solution for the policy scenario is an iterative process that finds the equilibrium prices and quantities under the new policy, while ensuring that the market clears and all constraints are satisfied.
The solution for the policy scenario saves the prices from the previous iteration to calculate the wedge for the next iteration, and continues until the prices converge to a stable equilibrium.


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
   new random numbers each run (`execseed = gmillisec(jnow)`).
If yes, build from `tj_noise_template.gms` instead of `tj_template.gms`
(see section 6).

**Step 8 - Confirm.** Show all inputs back in tables (regions, demand, supply,
transport costs, shock settings, and each scenario's changed inputs) with any
converted coefficients, and ask the user to confirm or correct them. Ask for
the model name and use it to create `models/<model-name>/`. Only then build
the model.

Rules:
- Never invent data. If the user just wants to try the agent, offer the
  illustrative data in the template and say clearly that it is made up.
- Check values as they come in: slopes and elasticities must be positive,
  prices and quantities non-negative, the cost table complete. Ask again if not.
- Converting elasticities to linear coefficients (show the result):
  demand `b = P0 / (|e_d| * Q0)`, `a = P0 + b*Q0`;
  supply `d = P0 / (e_s * Q0)`, `c = P0 - d*Q0`.

## 2. Model structure

Every model must solve a base case and at least one user-confirmed alternative
scenario. Add a scenario set and index scenario-specific variables, equations,
and results by it. Keep shared data and random shock draws common across cases;
change only the inputs the user assigned to each scenario. Do not copy
scenario-specific values into the shared base parameters or silently assume
that a scenario has no effect.

Always use the Takayama–Judge quadratic-programming formulation for
equilibrium solves. Do not solve policy scenarios as MCPs. Fix the policy
wedge during each QP solve, then update it outside the QP from the previous
solve's price marginals. For ad-valorem tariffs use
`w(i,j,t) = phi(i,j) * dembal.m(j,t)`; for export subsidies use
`w(i,j,t) = -sig(i,j) * supbal.m(i,t)`. Combine terms when both apply.
Iterate: solve the QP, calculate the target wedge, and update the wedge until
the maximum wedge change is below a documented tolerance. Use damping when
needed, set a maximum iteration count, and abort clearly if the iteration
does not converge. After convergence, solve once more with the final wedge
and check the policy-adjusted arbitrage conditions. Every individual solve
must remain a QCP/QP solve.

Keep the standard GAMS block order, each block commented:
`Sets` -> `Alias` -> `Parameters` / `Table` -> `Variables` -> `Equations`
(declaration, then definition) -> `Model` -> `Solve` -> reporting.

Variables (Positive):
- `x(i)` quantity supplied in region i
- `y(j)` quantity consumed in region j
- `q(i,j)` quantity shipped from i to j
- `nsp` (free) net social payoff

Objective - maximize Net Social Payoff:


**** Formulation for scenarios includes a wedge which is a function of phi and sig for tariffs and subsidies, respectively:
nsp =e= sum(j, a(j)*y(j) - 0.5*b(j)*y(j)*y(j))
             - sum(i, c(i)*x(i) + 0.5*d(i)*x(i)*x(i))
             - sum((i,j), t(i,j)*q(i,j))
             - sum((i,j)$(not sameas(i,j)), w(i,j)*q(i,j))

**** The formulation for the wedge is as follows:
- For tariffs: w(i,j)   =   phi(i,j)*dembal.m(j)
- For subsidies: w(i,j) = - sig(i,j)*supbal.m(i)
- For tariffs and subsidies together: w(i,j) = phi(i,j)*dembal.m(j) - sig(i,j)*supbal.m(i)  

Constraints:
- `dembal(j)`: `y(j) =l= sum(i, q(i,j))`
- `supbal(i)`: `sum(j, q(i,j)) =l= x(i)`
- Optional route capacity: `q.up(i,j) = cap(i,j);`

Solve with `solve tj using qcp maximizing nsp;` (convex QP, unique
equilibrium) for each fixed wedge. With an ad-valorem policy, repeat the QP
solve while updating the wedge from equation marginals until it converges.

Prices come from the equation marginals:
- `dembal.m(j)` = demand price in region j
- `supbal.m(i)` = supply price in region i

## 3. Validate the equilibrium

The script must check, and `abort` with a clear message if a check fails:
1. Model status is optimal (`tj.modelstat` = 1 or 2).
2. No arbitrage: `dembal.m(j) - supbal.m(i) - t(i,j) - w(i,j) <= 1e-4`
   for every route.
3. Active routes: where `q.l(i,j) > 1e-6`, price difference equals
   `t(i,j) + w(i,j)`.
4. Marginal prices match the curves: `dembal.m(j) = a(j) - b(j)*y.l(j)`
   where `y.l(j) > 0`.

If a check fails, explain why and fix the model before reporting.

## 4. Report the results

Build report parameters and `display` them as plain tables (no charts):
- **regional(r,\*)**: supply, demand, demand price, supply price, net exports.
- **flows(i,j)**: only non-zero shipments.
- **welfare(\*)**: consumer surplus `sum 0.5*b*y^2`, producer surplus
  `sum 0.5*d*x^2`, transport cost, total NSP.

Always save model outputs in the model's own folder. Each completed run must
create:
- `tj_model.gms`: runnable model source with all input data and scenario
  definitions at the top.
- `tj_model.lst`: GAMS listing from the actual completed run, including
  validation results and a short plain-language summary of the comparison.
- `tj_results.gdx`: model inputs and solved variables/results for every
  scenario and period.
- `tj_results.xlsx`: one workbook created by `gdxxrw` from `tj_results.gdx`.
  Include scenario- and time-indexed prices, supply, demand, shocks, trade
  flows, welfare, price summaries, and the model's input parameters on
  separate worksheets.

Keep the GAMS reporting/export section simple: create report parameters with
the scenario, time, and region dimensions, unload them once to GDX, and use
`gdxxrw` to write the symbols to the workbook. Do not write CSV files or use
GAMS `put` statements or explicit GAMS loops to format or export rows. Use a
small `gdxxrw` command file to map symbols to workbook sheets when needed.
When a graphic is requested, put its complete Python plotting implementation
inside the `.gms` source using GAMS execution-time embedded code:
`embeddedCode Python:` ... `endEmbeddedCode`. Read the solved symbols directly
through `gams.get(...)`; do not create or depend on a separate plotting script
or intermediate CSV files. The embedded Python may loop through observations
to draw the graphic; avoid explicit GAMS loops for report/export formatting.
Write the requested graphic (for example `scenario_comparison.svg`) beside
the model and check that it was created successfully.

After running, summarise in 2-4 sentences: which regions export, where prices
are highest, and why.

## 5. Stochastic version with random shocks

Use when the user answered yes in Step 7. Start from `tj_noise_template.gms`.

- Add a time set `t` (one market equilibrium per period, no storage).
  Transport costs are named `tc(i,j)` in this version so they don't clash
  with the time set.
- Set the switches at the top: `useNoise`, `noiseType` (1 white noise,
  2 random walk), `sigma`, `fixedSeed`, and the seed value.
- Shocks: `e(r,t) = normal(0, sigma)`; for a random walk,
  `u(r,t) = u(r,t-1) + e(r,t)`; for white noise, `u = e`.
- Shifted intercepts: supply `ct(i,t) = c(i) + u(i,t)`; for demand shocks
  use a separate draw and `at(j,t) = a(j) + u_d(j,t)`. Use a region filter
  if only some regions are shocked.
- Index every variable and equation by `t` and sum the objective over `t`.
- Run the same equilibrium checks for every period.
- Warn the user if a shifted intercept becomes negative, especially with a
  random walk over many periods.
- Report time-series tables (rows = periods): price by region, supply,
  demand, and the shock itself; plus a summary table with mean, standard
  deviation, min and max price per region. Save the scenario/time-indexed
  parameters to GDX with `execute_unload`, then export the workbook using
  `gdxxrw` without `put`-formatted CSVs or explicit export loops. Use identical
  generated shock draws for every policy scenario.

## 6. Extensions (only when asked)

- **Multiple commodities**: add a set `k` and index every variable,
  parameter and equation by it.
- **Temporal model**: add a time set `tt`, storage variables and a storage
  cost between periods (Takayama-Judge spatial-temporal version).
- **Policy scenarios**: tariffs or subsidies - solve the confirmed base case
  and at least one user-defined alternative in the same file using the
  iterated-QP wedge procedure above. Do not switch to MCP for ad-valorem
  policies. Make the scenario comparison standard in every model.

## Deliverables

- Ask for a model name and save all deliverables under
  `models/<model-name>/`.
- `tj_model.gms`: complete, runnable GAMS file with all data and the base and
  user-confirmed alternative scenario definitions at the top.
- Always create and verify `tj_model.lst`, `tj_results.gdx`, and
  `tj_results.xlsx`. Use `gdxxrw` to export the scenario/time-indexed results
  and inputs to separate worksheets in the workbook.
- Do not create per-table CSV files or explicit GAMS `put` loops for exports.
- When a plot is requested, generate it with Python embedded directly in the
  GAMS source using execution-time embedded code; do not use a separate
  Python plot script or CSV intermediates.
- The result tables (from the `.lst` file) summarised in the chat.
- Short instructions on how to change the data and rerun.
- For stochastic models, also report a summary table with mean, standard
  deviation, minimum, and maximum price per region and scenario.
- Add comments explaining model blocks and equations, and include a short,
  plain-language comparison summary at the end of the `.lst` file.
