# Quantopian Algorithmic Trading

This is a Python-based algorithmic trading project that aims to create a market-neutral portfolio by trading stocks and ETFs based on a quarterly rebalancing schedule.

## Strategy

The trading algorithm identifies newly public stocks and trades them against an offsetting ETF to achieve a market-neutral position. ETFs are chosen based on their sector codes. The algorithm relies on a market- and cash-neutral long/short strategy of shorting an IPO-ed stock while longing an offsetting ETF. The strategy is designed to remove any correlation with the overall market and focus on relative mispricing between securities through alpha capture.

## Backtesting Results

Backtesting results show that the strategy has generated statistically significant excess returns at the 5% level. However, returns decrease as the short-selling rate increases, and the reported returns should be interpreted as a "maximum bound" for returns. At an annualized short-selling rate of 1.84%, the strategy will break even, and excess returns will not be earned. Therefore, caution should be exercised when interpreting the backtested results, and the strategy should be further tested and evaluated before being implemented in a real-world trading scenario.

## Implementation

The script starts by importing the necessary modules and defining variables such as rebalancing schedule and maximum position size. The quarterly rebalancing schedule ensures that the algorithm stays up to date with recent IPOs and keeps the portfolio market-neutral.

## Conclusion

Overall, this algorithmic trading project provides a strategy for creating a market-neutral portfolio using a long/short strategy and ETFs. The project could be further developed and tested to implement in real-world trading scenarios.
