# Quantopian Algorithmic Trading Project
This is a Python script to execute an algorithmic trading strategy using Quantopian's platform. The script is designed to short recent IPOs and hedge by going long in the corresponding sector ETF. The positions are held for 4 years after the IPO, and the performance of each pair trade is recorded.

## Key Concepts
- Quantopian: Quantopian is a free, online platform that provides the data, the backtester, and the analysis tools for individuals to develop algorithmic trading strategies.

- IPO (Initial Public Offering): IPO is the process by which a private company can go public by sale of its stocks to the general public. This script specifically targets companies that have gone public within the last three months.

- ETF (Exchange Traded Fund): ETFs are marketable securities that track an index, a commodity, bonds, or a basket of assets like an index fund. The script uses sector ETFs to hedge the short positions taken in the IPOs.

- Short Selling: Short selling is the sale of a security that the seller does not own. In this script, we short sell stocks of the recently IPO'd companies.

- Hedging: Hedging is making an investment to reduce the risk of adverse price movements in an asset. In this script, we hedge our short positions by going long in the corresponding sector ETF.

- Pair Trading: Pair trading is a market neutral trading strategy enabling traders to profit from virtually any market conditions. In this script, each "pair" consists of a short position in an IPO and a long position in a corresponding sector ETF.

## Usage
1. Set up a Quantopian account.
2. Copy this script into the Quantopian algorithm window.
3. Run a backtest on the desired date range.

## Components
- initialize(context): Called once at the start of the algorithm. Defines the base universe of securities, commissions, and schedules the functions to be executed.

- make_pipeline(): Creates a pipeline that gets the necessary data for each security in the base universe.

- before_trading_start(context, data): Called every day before market open. It fetches the pipeline data for the securities that we are interested in trading.

- rebalance(context, data): Executes orders according to the schedule defined in initialize(context). Handles both the opening and closing of positions.

- record_vars(context, data): Called at the end of each day to record and plot variables of interest.

- handle_data(context, data): Called every minute, but currently does nothing.

## Disclaimer
The Quantopian platform has been closed for live trading as of September 2020. 