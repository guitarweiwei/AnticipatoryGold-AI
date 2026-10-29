// AnticipatoryGold AI / FvgGold integration: RESEARCH SIGNALS ONLY.
// No trade requests, no changes to EntryRiskPolicyApproved() or existing locks.
#ifndef __AG_FVG_GRID_RESEARCH__
#define __AG_FVG_GRID_RESEARCH__
enum AGResearchMode { AG_AI_GRID=0, AG_FVG_GRID=1, AG_HYBRID_GRID=2 };
struct AGFVG { int direction; double low; double high; datetime formed; double score; bool ob_overlap; };
struct AGGridPlan { int direction; int layers; double entry[10]; double lots[10]; double stop; bool valid; };
double AGClamp(double v,double lo,double hi){return MathMax(lo,MathMin(hi,v));}
// Use only CLOSED candles: shift 3 (first), 2 (impulse), 1 (third).
bool AGDetectClosedFVG(string symbol,ENUM_TIMEFRAMES tf,double min_gap_points,AGFVG &out)
{
 double h1=iHigh(symbol,tf,3),l1=iLow(symbol,tf,3);
 double h3=iHigh(symbol,tf,1),l3=iLow(symbol,tf,1);
 datetime t=iTime(symbol,tf,2);
 double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
 if(t<=0||point<=0||h1<=0||l1<=0||h3<=0||l3<=0)return false;
 int dir=0;double low=0,high=0;
 if(l3>h1){dir=1;low=h1;high=l3;}
 else if(h3<l1){dir=-1;low=h3;high=l1;}
 if(dir==0||(high-low)/point<min_gap_points)return false;
 out.direction=dir;out.low=low;out.high=high;out.formed=t;
 out.score=0;out.ob_overlap=false;return true;
}
// Conservative OB proxy: most recent opposite candle preceding an impulse.
// A candidate is not an institutionally verified order block.
bool AGFindOBConfluence(string symbol,ENUM_TIMEFRAMES tf,const AGFVG &fvg,
                        int lookback,double max_distance_points)
{
 double point=SymbolInfoDouble(symbol,SYMBOL_POINT);
 if(point<=0||lookback<4)return false;
 for(int shift=3;shift<=lookback;shift++){
   double o=iOpen(symbol,tf,shift),c=iClose(symbol,tf,shift);
   double h=iHigh(symbol,tf,shift),l=iLow(symbol,tf,shift);
   if(h<=0||l<=0)continue;
   bool opposite=(fvg.direction==1 ? c<o : c>o);
   if(opposite && h+max_distance_points*point>=fvg.low &&
      l-max_distance_points*point<=fvg.high)return true;
 }
 return false;
}
// Scores are heuristics, NOT calibrated probabilities; capped at 100.
double AGScoreFVG(const AGFVG &fvg,double atr,int htf_bias,int age_bars,
                  int max_age,bool premium_discount_ok)
{
 if(atr<=0||max_age<1||age_bars<1||age_bars>max_age)return 0;
 double gap=(fvg.high-fvg.low)/atr;
 double score=30.0*AGClamp(gap,0,1)
             +30.0*AGClamp(gap/1.5,0,1)
             +(htf_bias==fvg.direction?20.0:0.0)
             +10.0*AGClamp(1.0-(double)age_bars/max_age,0,1)
             +(premium_discount_ok?10.0:0.0)
             +(fvg.ob_overlap?20.0:0.0);
 return AGClamp(score,0,100);
}
// Planner only: never opens orders. Ten layers maximum, equal size (no martingale).
// The stop is common across layers and risk is checked on the WORST filled basket.
bool AGBuildGrid(string symbol,int direction,double first_entry,double atr,
                 double atr_step,int requested_layers,double fixed_lot,
                 double stop_price,double max_basket_risk_money,AGGridPlan &plan)
{
 plan.valid=false;plan.layers=0;
 if(direction!=1&&direction!=-1)return false;
 if(atr<=0||atr_step<=0||requested_layers<1||requested_layers>10||
    fixed_lot<=0||max_basket_risk_money<=0)return false;
 double vmin=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MIN);
 double vstep=SymbolInfoDouble(symbol,SYMBOL_VOLUME_STEP);
 double vmax=SymbolInfoDouble(symbol,SYMBOL_VOLUME_MAX);
 if(vmin<=0||vstep<=0||vmax<=0||fixed_lot<vmin||fixed_lot>vmax)return false;
 double steps=fixed_lot/vstep;
 if(MathAbs(steps-MathRound(steps))>1e-6)return false;
 plan.direction=direction;plan.stop=stop_price;
 double total_risk=0;
 for(int i=0;i<requested_layers;i++){
   double entry=first_entry-direction*i*atr*atr_step;
   if((direction==1&&stop_price>=entry)||(direction==-1&&stop_price<=entry))return false;
   double pnl=0;
   if(!OrderCalcProfit(direction==1?ORDER_TYPE_BUY:ORDER_TYPE_SELL,
                       symbol,fixed_lot,entry,stop_price,pnl))return false;
   if(!MathIsValidNumber(pnl)||pnl>=0)return false;
   total_risk+=-pnl;
   plan.entry[i]=entry;plan.lots[i]=fixed_lot;
 }
 if(total_risk>max_basket_risk_money)return false;
 plan.layers=requested_layers;plan.valid=true;return true;
}

// Adaptive selection is advisory only. Confidence must be a finite 0..1 score,
// not an uncalibrated FVG score; low confidence means HOLD.
// Volatility is expressed as ATR / midprice, not raw dollar ATR.
int AGSelectAdaptiveLayers(double confidence,double atr,double midprice,
                           double available_risk_money,double minimum_layer_risk_money,
                           int configured_max_layers)
{
 if(!MathIsValidNumber(confidence)||!MathIsValidNumber(atr)||
    !MathIsValidNumber(midprice)||!MathIsValidNumber(available_risk_money)||
    !MathIsValidNumber(minimum_layer_risk_money))return 0;
 if(confidence<0.58||confidence>1.0||atr<=0||midprice<=0||
    available_risk_money<=0||minimum_layer_risk_money<=0)return 0;
 int cap=MathMin(10,MathMax(0,configured_max_layers));
 if(cap==0)return 0;
 double atr_ratio=atr/midprice;
 // Higher volatility reduces the permitted number of layers.
 double volatility_factor=(atr_ratio>=0.008?0.25:(atr_ratio>=0.004?0.5:1.0));
 double strength=(confidence-0.58)/(1.0-0.58);
 int signal_layers=1+(int)MathFloor(strength*9.0*volatility_factor);
 int affordable=(int)MathFloor(available_risk_money/minimum_layer_risk_money);
 return MathMax(0,MathMin(cap,MathMin(signal_layers,affordable)));
}
// Conservative integration: first determine candidate count, then call
// AGBuildGrid() with the actual stop and symbol for full worst-case risk.
// If the complete basket fails, reduce the count and recompute; never force
// a minimum lot or assume that a per-layer estimate is sufficient.
bool AGBuildAdaptiveGrid(string symbol,int direction,double first_entry,double atr,
                         double atr_step,double confidence,double available_risk_money,
                         double min_layer_risk_estimate,int max_layers,double lot,
                         double stop_price,AGGridPlan &plan)
{
 int n=AGSelectAdaptiveLayers(confidence,atr,first_entry,
                             available_risk_money,min_layer_risk_estimate,max_layers);
 for(;n>=1;n--)
   if(AGBuildGrid(symbol,direction,first_entry,atr,atr_step,n,lot,
                  stop_price,available_risk_money,plan))return true;
 plan.valid=false;plan.layers=0;return false;
}
#endif
