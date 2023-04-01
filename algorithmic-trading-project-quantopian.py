"""
Quantopian Algorithmic Trading project
"""

import quantopian.algorithm as algo
from quantopian.pipeline import Pipeline
from quantopian.pipeline.data.builtin import USEquityPricing
from quantopian.pipeline.filters import Q3000US, StaticAssets
from quantopian.pipeline.data.morningstar import Fundamentals
from quantopian.pipeline.data.factset import EquityMetadata
from datetime import date

MONTH_STARTS = [3, 6, 9, 12]

MAX_POSITION = 0.025

ETF_SECTOR_TICKER = {101: symbol('XLB'), 102: symbol('XLY'),
                     103: symbol('XLF'), 206: symbol('XLV'),
                     207: symbol('XLU'), 309: symbol('XLE'),
                     310: symbol('XLI'), 311: symbol('XLK'),
                     205: symbol('XLP'), 308: symbol('XLC'),
                     104: symbol('XLRE')}

def initialize(context):
    """
    Called once at the start of the algorithm.
    """
    # Rebalance every 3 months, 1 hour after market open.
    algo.schedule_function(
        rebalance,
        algo.date_rules.month_end(),
        algo.time_rules.market_open(hours=1),
    )

    # Record tracking variables at the end of each day.
    algo.schedule_function(
        record_vars,
        algo.date_rules.every_day(),
        algo.time_rules.market_close(),
    )

    # Create our dynamic stock selector.
    algo.attach_pipeline(make_pipeline(), 'pipeline')

    # Include slippage of large positions, ignored for smaller positions
    set_commission(commission.PerDollar(cost=0.0010))

    context.positions_taken = {}
    context.pairs_taken = 0
    context.pairs_return = 0

def make_pipeline():
    """
    A function to create our dynamic stock selector (pipeline). 
    Documentation on pipeline can be found here:
    https://www.quantopian.com/help#pipeline-title
    """

    # Find IPO dates for stocks
    ipo_date = Fundamentals.ipo_date.latest

    # Base universe set to the QTradableStocksUS
    base_universe = Q3000US()

    # Add ETFs to the base universe
    etf_universe = StaticAssets(symbols('XLB', 'XLY', 'XLF', 'XLV',
                                        'XLU', 'XLE', 'XLI', 'XLK',
                                        'XLP', 'XLC', 'XLRE'))

    # Combine the two universe
    combined_universe = base_universe | etf_universe

    # Factor of yesterday's close price.
    yesterday_close = USEquityPricing.close.latest

    # Morningstar sector codes for each stock
    sector_code = Fundamentals.morningstar_sector_code.latest

    pipe = Pipeline(
        columns={
             'close': yesterday_close,
             'ipo_date': ipo_date,
             'sector_code': sector_code
        },
        screen=(combined_universe)
    )
    return pipe
        
def before_trading_start(context, data):
    """
    Called every day before market open.
    """
    context.output = algo.pipeline_output('pipeline')

    # These are the securities that we are interested in trading each day.
    context.security_list = context.output.index

def rebalance(context, data):
    """
    Execute orders according to our schedule_function() timing.
    """

    # To close out ETF positions if the shorted stock gets delisted
    client_side_securities = set(context.positions_taken.keys())
    
    server_side_all_securities = set([sec.sid for sec in
                                      context.portfolio.positions.keys()])
    
    ETF_securities = set([etf.sid for etf in ETF_SECTOR_TICKER.values()])

    server_side_securities = server_side_all_securities - ETF_securities


    delisted_securities = client_side_securities.difference(
        server_side_securities)

    for security in delisted_securities:

        ETF_amount = context.positions_taken[security][1]
        sector_code = context.positions_taken[security][2]
        ETF_ticker = ETF_SECTOR_TICKER.get(sector_code)
        ETF_price = context.output.at[ETF_ticker, 'close']
        context.positions_taken.pop(security)
       
        order(ETF_ticker, -ETF_amount)

        log.info("Security with SID {} was delisted,\
                 closing offsetting ETF {} for {} ETFs @ ${}"
                 .format(security, ETF_ticker.symbol, ETF_amount, ETF_price)) 

    # Early return if current month is not in QUARTER_STARTS
    month_number = get_datetime().date().month
    if month_number not in MONTH_STARTS:
        return None

    order_price = context.portfolio.starting_cash * MAX_POSITION

    for security in context.security_list:

        ipo_date = context.output.at[security, 'ipo_date']
        
        # Remove securities that do not have data on IPO dates 
        # and remove intraday information on IPO time
        if str(ipo_date) is not "NaT":

            ipo_year = int(str(ipo_date)[:4])
            ipo_month = int(str(ipo_date)[5:7])

            backtesting_year = int(get_datetime().date().year)
            backtesting_month = int(get_datetime().date().month)
            backtesting_day = int(get_datetime().date().day)

            # Find all IPOs of companies within the last 3 months
            if ipo_year == backtesting_year:
                if ipo_month >= backtesting_month - 2:
            
                    # Find the ETF sid for the offsetting portfolio
                    sector_code = context.output.at[security, 'sector_code']
                    ETF_ticker = ETF_SECTOR_TICKER.get(sector_code)
                    
                    # Extra conditioning for XLRE and XLC ETFs 
                    # since traded since 2015-10-12 & 2018-06-19 respectively
                    if sector_code == 104:
                        if (backtesting_year >= 2015) and\
                            (backtesting_month >= 10) and\
                                (backtesting_day >= 12):
                            True
                        else:
                            log.info("Failed to form pairs for security {}\
                                     due to non-existing XLRE ETF"
                                     .format(security.symbol))
                            continue

                    if sector_code == 308:

                        if (backtesting_year >= 2018) and\
                            (backtesting_month >= 6) and\
                                (backtesting_day >= 19):
                            True
                        
                        else:
                            log.info("Failed to form pairs for security {}\
                                due to non-existing XLC ETF"
                                .format(security.symbol))
                            continue

                    if ETF_ticker is not None:

                        # Short the IPO company's stocks
                        share_price = context.output.at[security, 'close']
                        share_amount = order_price // share_price
                        order(security, -share_amount)
                        
                        # Long the offsetting ETF
                        ETF_price = context.output.at[ETF_ticker, 'close']
                        ETF_amount = order_price // ETF_price
                        order(ETF_ticker, ETF_amount)
                        
                        context.positions_taken[security.sid] = (
                            [share_amount, ETF_amount, sector_code,
                            share_amount * share_price]
                        )
                        log.info("Opening position. Short security {} for {}\
                                shares @ ${}. Long ETF {} for {}ETFs @ ${}"
                                .format(security.symbol, share_amount,
                                               share_price, ETF_ticker.symbol,
                                               ETF_amount, ETF_price))

    for security in context.portfolio.positions.keys():

        # Get IPO date if the current security is not an ETF
        try:
            ipo_date = context.output.at[security, 'ipo_date']

            # Close out positions on the 4th year after IPO
            ipo_year = int(str(ipo_date)[:4])
            backtesting_year = int(get_datetime().date().year)

            if (ipo_year + 4) == backtesting_year:
                share_amount = context.positions_taken[security.sid][0]
                share_price = context.output.at[security, 'close']

                order(security, share_amount)

                # Close out the offseting ETF
                ETF_amount = context.positions_taken[security.sid][1]
                sector_code = context.positions_taken[security.sid][2]
                ETF_ticker = ETF_SECTOR_TICKER.get(sector_code)
                
                ETF_price = context.output.at[ETF_ticker, 'close']
                
                order(ETF_ticker, -ETF_amount)
                
                log.info("Closing position. Long security {} for {}\
                    shares @ ${}. Short ETF {} for {} ETFs @ ${}"
                    .format(security.symbol, share_amount, share_price,
                            ETF_ticker.symbol, ETF_amount, ETF_price))

                # Calculate the return generate by each pair

                closing_profit = (ETF_amount * ETF_price) - (share_amount *
                                                             share_price)
                initial_borrowing = context.positions_taken[security.sid][3]
                context.positions_taken.pop(security.sid)
                closing_return = closing_profit / initial_borrowing
                
                # Calculate the number of days the pair was open
                ipo_year = int(str(ipo_date)[:4])
                ipo_month = int(str(ipo_date)[5:7])
                ipo_day = int(str(ipo_date)[8:10])

                backtesting_year = int(get_datetime().date().year)
                backtesting_month = int(get_datetime().date().month)
                backtesting_day = int(get_datetime().date().day)

                d0 = date(ipo_year, ipo_month, ipo_day)
                d1 = date(backtesting_year, backtesting_month, backtesting_day)

                time_open = (d1 - d0)
                days_open = time_open.days
                
                # Calculate the breakeven per day return
                breakeven_return = (1 + closing_return) ** (1 / days_open) - 1

                # Add cumulative return * 100 million to context.pairs_return
                # due to Quantopian not being accurate with decimal places
                if str(breakeven_return) is not 'nan':
                    int_return = int(breakeven_return * 100000000)
                    context.pairs_return += int_return
                    context.pairs_taken += 1

        except (KeyError, ValueError):
            continue

def record_vars(context, data):
    """
    Plot variables at the end of each day.
    """
    record("Cash", context.portfolio.cash)
    record("Positions", len(context.portfolio.positions))

def handle_data(context, data):
    """
    Called every minute.
    """
    pass