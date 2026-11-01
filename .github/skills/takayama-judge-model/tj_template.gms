$title Takayama-Judge Spatial Price Equilibrium (template)
* -----------------------------------------------------------------
* Single commodity, linear demand and supply, unit transport costs.
* The data below is ILLUSTRATIVE - replace it with the user's data.
* -----------------------------------------------------------------

*--- Sets ----------------------------------------------------------
Set r  regions / north, centre, south /;
Alias (r, i, j);

*--- Data ----------------------------------------------------------
* Inverse demand: price = a - b*quantity
* Inverse supply: price = c + d*quantity
Parameters
   a(r)  demand intercept  / north 100, centre 120, south  90 /
   b(r)  demand slope      / north 1.0, centre 1.5, south 0.8 /
   c(r)  supply intercept  / north  20, centre  40, south  30 /
   d(r)  supply slope      / north 0.5, centre 1.0, south 0.7 /;

Table t(i,j)  unit transport cost from i to j
            north   centre   south
   north      0       5        9
   centre     5       0        6
   south      9       6        0 ;

*--- Variables -----------------------------------------------------
Positive Variables
   x(i)     quantity supplied in region i
   y(j)     quantity consumed in region j
   q(i,j)   quantity shipped from i to j;
Variable
   nsp      net social payoff;

*--- Equations -----------------------------------------------------
Equations
   obj        net social payoff definition
   dembal(j)  demand cannot exceed what is shipped in
   supbal(i)  shipments out cannot exceed supply;

obj..        nsp =e= sum(j, a(j)*y(j) - 0.5*b(j)*y(j)*y(j))
                   - sum(i, c(i)*x(i) + 0.5*d(i)*x(i)*x(i))
                   - sum((i,j), t(i,j)*q(i,j));

dembal(j)..  y(j) =l= sum(i, q(i,j));

supbal(i)..  sum(j, q(i,j)) =l= x(i);

*--- Model and solve -----------------------------------------------
Model tj / all /;
solve tj using qcp maximizing nsp;

abort$(tj.modelstat <> 1 and tj.modelstat <> 2) "Model not solved to optimality";

*--- Equilibrium checks --------------------------------------------
Scalar tol tolerance / 1e-4 /;
Parameter arb(i,j)  price difference minus transport cost (must be <= 0);
arb(i,j) = dembal.m(j) - supbal.m(i) - t(i,j);

abort$(smax((i,j), arb(i,j)) > tol)
   "No-arbitrage condition violated", arb;
abort$(smax((i,j)$(q.l(i,j) > 1e-6), abs(arb(i,j))) > tol)
   "Active route without zero arbitrage margin", arb;
abort$(smax(j$(y.l(j) > 1e-6), abs(dembal.m(j) - (a(j) - b(j)*y.l(j)))) > tol)
   "Demand price does not match demand curve";

*--- Reporting -----------------------------------------------------
Parameters
   regional(r,*)  regional results
   flows(i,j)     non-zero shipments
   welfare(*)     welfare summary;

regional(r,'supply')    = x.l(r);
regional(r,'demand')    = y.l(r);
regional(r,'dem_price') = dembal.m(r);
regional(r,'sup_price') = supbal.m(r);
regional(r,'net_exp')   = x.l(r) - y.l(r);

flows(i,j)$(q.l(i,j) > 1e-6) = q.l(i,j);

welfare('consumer_surplus') = sum(j, 0.5*b(j)*sqr(y.l(j)));
welfare('producer_surplus') = sum(i, 0.5*d(i)*sqr(x.l(i)));
welfare('transport_cost')   = sum((i,j), t(i,j)*q.l(i,j));
welfare('net_social_payoff') = nsp.l;

Option regional:2, flows:2, welfare:2;
display regional, flows, welfare;
