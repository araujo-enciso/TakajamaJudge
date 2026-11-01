$title Takayama-Judge model with random shocks (template)
* -----------------------------------------------------------------
* One equilibrium per period. A random shock moves the intercept of
* the inverse supply function: price = ct(i,t) + d(i)*quantity.
*   noiseType = 1 : white noise   u(i,t) = e(i,t)
*   noiseType = 2 : random walk   u(i,t) = u(i,t-1) + e(i,t)
* The data below is ILLUSTRATIVE - replace it with the user's data.
* -----------------------------------------------------------------

*--- Shock settings ------------------------------------------------
Scalars
   useNoise   1 = add random shocks  0 = no shocks       / 1 /
   noiseType  1 = white noise        2 = random walk     / 2 /
   sigma      standard deviation of each shock           / 1 /
   fixedSeed  1 = same draws every run  0 = new draws    / 1 /
   seedValue  seed used when fixedSeed = 1               / 12345 /;

if(fixedSeed = 1,
   execseed = seedValue;
else
   execseed = gmillisec(jnow);
);

*--- Sets ----------------------------------------------------------
Sets
   t  time periods / 1*500 /
   r  regions      / r1, r2 /;
Alias (r, i, j);

*--- Data ----------------------------------------------------------
* Inverse demand: price = a - b*quantity
* Inverse supply: price = c + d*quantity  (c is shocked over time)
Parameters
   a(r)  demand intercept  / r1 20,  r2 20  /
   b(r)  demand slope      / r1 0.1, r2 0.2 /
   c(r)  supply intercept  / r1 5,   r2 2.5 /
   d(r)  supply slope      / r1 1,   r2 0.5 /;

Table tc(i,j)  unit transport cost from i to j
          r1    r2
   r1      0     2
   r2      2     0 ;

*--- Random shocks -------------------------------------------------
Parameters
   e(r,t)   shock drawn in period t
   u(r,t)   shock applied in period t (white noise or cumulative)
   ct(r,t)  supply intercept in period t;

e(r,t) = useNoise * normal(0, sigma);
u(r,t) = e(r,t);
if(noiseType = 2,
   loop(t$(ord(t) > 1), u(r,t) = u(r,t-1) + e(r,t));
);
ct(r,t) = c(r) + u(r,t);

* Warn (do not stop) if a shifted intercept becomes negative
Scalar minIntercept lowest shifted supply intercept;
minIntercept = smin((r,t), ct(r,t));
display$(minIntercept < 0) "WARNING: a supply intercept is negative", minIntercept;

*--- Variables -----------------------------------------------------
Positive Variables
   x(i,t)     quantity supplied in region i, period t
   y(j,t)     quantity consumed in region j, period t
   q(i,j,t)   quantity shipped from i to j, period t;
Variable
   nsp        net social payoff over all periods;

*--- Equations -----------------------------------------------------
Equations
   obj          net social payoff definition
   dembal(j,t)  demand cannot exceed what is shipped in
   supbal(i,t)  shipments out cannot exceed supply;

obj..          nsp =e= sum(t,
                         sum(j, a(j)*y(j,t) - 0.5*b(j)*y(j,t)*y(j,t))
                       - sum(i, ct(i,t)*x(i,t) + 0.5*d(i)*x(i,t)*x(i,t))
                       - sum((i,j), tc(i,j)*q(i,j,t)) );

dembal(j,t)..  y(j,t) =l= sum(i, q(i,j,t));

supbal(i,t)..  sum(j, q(i,j,t)) =l= x(i,t);

*--- Model and solve -----------------------------------------------
Model tjnoise / all /;
tjnoise.reslim = 100000;
solve tjnoise using qcp maximizing nsp;

abort$(tjnoise.modelstat <> 1 and tjnoise.modelstat <> 2) "Model not solved to optimality";

*--- Equilibrium checks (every period) -----------------------------
Scalar tol tolerance / 1e-4 /;
Parameter arb(i,j,t)  price difference minus transport cost (must be <= 0);
arb(i,j,t) = dembal.m(j,t) - supbal.m(i,t) - tc(i,j);

abort$(smax((i,j,t), arb(i,j,t)) > tol)
   "No-arbitrage condition violated";
abort$(smax((i,j,t)$(q.l(i,j,t) > 1e-6), abs(arb(i,j,t))) > tol)
   "Active route without zero arbitrage margin";

*--- Reporting: time series (rows = periods) -----------------------
Parameters
   price(t,r)     demand price by period
   supply(t,r)    quantity supplied by period
   demand(t,r)    quantity consumed by period
   shock(t,r)     shock applied to the supply intercept
   summary(r,*)   price statistics over all periods;

price(t,r)  = dembal.m(r,t);
supply(t,r) = x.l(r,t);
demand(t,r) = y.l(r,t);
shock(t,r)  = u(r,t);

summary(r,'mean') = sum(t, price(t,r)) / card(t);
summary(r,'stdev') = sqrt(sum(t, sqr(price(t,r) - summary(r,'mean'))) / (card(t) - 1));
summary(r,'min')  = smin(t, price(t,r));
summary(r,'max')  = smax(t, price(t,r));

Option price:3, supply:3, demand:3, shock:3, summary:3;
display summary, price, supply, demand, shock;

*--- Save everything for later analysis ----------------------------
execute_unload 'results', t, r, a, b, c, d, tc, e, u, ct,
                          x, y, q, dembal, supbal, price, supply, demand, shock, summary;
