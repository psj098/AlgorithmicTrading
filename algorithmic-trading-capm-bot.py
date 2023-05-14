"""
CAPM Bot - Market Trading Agent using CAPM Model

This script implements the CAPM Bot, a market trading agent that uses 
the Capital Asset Pricing Model (CAPM) to make trading decisions. 
The bot participates in a financial market and aims to optimize its 
portfolio by maximizing its expected payoff while managing the risk.

The bot connects to the market using the `fmclient` library and executes buy 
and sell orders based on the performance calculations derived from the CAPM 
model. It also incorporates market maker functionalities in the last 
5 minutes of the session.

The script defines the `CAPMBot` class, which inherits from the `Agent` 
class provided by the `fmclient` library. It overrides several methods 
from the base class to implement the bot's behavior.
"""

import copy
import threading
import time
from random import *
from typing import List
from itertools import combinations
from fmclient import Agent, Session, Market
from fmclient import Order, OrderSide, OrderType

def in_dollar(cent):
    return cent / 100

class CAPMBot(Agent):

    def __init__(self, account, email, password, marketplace_id,
                 risk_penalty=0.007, session_time=20):
        super().__init__(account, email, password, marketplace_id,
                         name="CAPM Bot")
        
        # Payoff and market information
        self._payoffs = {}
        self._market_ids = {}

        # Parameters and conditions
        self._risk_penalty = risk_penalty
        self._session_time = session_time
        self._time_condition_mm = (session_time * 3 / 40000) * 60

        # Financial information
        self._cash = 0
        self._cash_available = 0
        self._num_states = 0

        # Holdings and performance
        self._current_performance = 0
        self._current_holdings = {}
        self._current_holdings_item = {}
        self._current_units_available = {}

        # Variance and covariance
        self._variances = {}
        self._covariances = {}

        # Order book and best bid/ask
        self._best_bid = {}
        self._best_ask = {}
        self._order_book = []
        self._processed_list = []

        # Trading combinations and session status
        self._combination = []
        self._session_open = False
        self._waiting_for_server = False
        self._waiting_for_mm = False
        self._list_used_up = False

        # Timing and market maker conditions
        self._time_start = 0
        self._time_last_order_sent = 0
        self._mm_condition_1 = 0
        self._mm_condition_2 = 0

        # Other variables
        self._tick = 0

    def initialised(self):
        """
        Initializes the agent by creating the payoff table, 
        accessing market IDs, and calculating the number of states.
        """
        # Create payoff table
        for market_id, market_info in self.markets.items():
            self._market_ids[market_id] = market_info
            security = market_info.item
            description = market_info.description
            self._payoffs[security] = [int(a) for a in description.split(",")]

        # Access market_id by passing in name of security through dictionary
        self.inform(self._market_ids)
        self.inform(self._payoffs)

        # Number of states (specified as 4)
        self._num_states = len(self._payoffs)
        self.inform("Number of possible states: " + str(self._num_states))

    def _payoff_variance_covariance(self, holding):
        """
        Calculates the overall variance of the holdings 
        based on variances and covariances.
        """
        payoff_variance = 0

        for market in holding:
            payoff_variance += (holding[market] ** 2) *\
            (self._variances[market])
        for two_markets in self._covariances:
            split = two_markets.split('+')
            payoff_variance += (
                2
                * holding[int(split[0])]
                * holding[int(split[1])]
                * self._covariances[two_markets]
            )
        return payoff_variance

    def _make_variance(self):
        """
        Calculates variances for each market based on the payoffs.
        """
        self._variances = {}
        for market in self._market_ids.keys():
            self._variances[market] = self._calculate_variance(
                self._payoffs[self._market_ids[market].item]
            )

    def _calculate_variance(self, payoff):
        """
        Calculates the variance of a given payoff list.

        Parameters:
        - payoff (list): List of payoff outcomes for a market

        Returns:
        - variance (float): Variance of the payoff list
        """
        squared_payoff = [outcome ** 2 for outcome in payoff]
        variance = ((1 / self._num_states) * sum(squared_payoff)) - \
                ((1 / (self._num_states ** 2)) * (sum(payoff) ** 2))
        dollar_scaled_variance = variance / 10000
        return dollar_scaled_variance

    def _make_covariance(self):
        """
        Calculates and stores the cov between holdings for different markets.
        """
        for id1 in self._current_holdings:
            for id2 in self._current_holdings:
                sorted_ids = sorted([id1, id2])
                combine_ids = str(sorted_ids[0]) + '+' + str(sorted_ids[1])
                if id1 != id2:
                    self._covariances[combine_ids] = \
                        self._calculate_covariance(
                            self._market_ids[id1].item,
                            self._market_ids[id2].item
                        )

    def _expected_return(self, item_name):
        """
        Calculates the expected return of a given item.
        """
        expected_return = 0
        payoff_item = self._payoffs[item_name]
        for state in payoff_item:
            expected_return += state * (1 / self._num_states)
        return expected_return

    def _calculate_covariance(self, item1, item2):
        """
        Calculates the covariance between two items based on their payoffs.
        """
        payoff1 = self._payoffs[item1]
        payoff2 = self._payoffs[item2]
        er1 = self._expected_return(item1)
        er2 = self._expected_return(item2)
        multiply_payoff_state = [payoff1[state] * payoff2[state] for state in range(self._num_states)]
        cov = (1 / self._num_states) * sum(multiply_payoff_state) - (er1 * er2)
        dollar_scaled_cov = cov / 10000
        return dollar_scaled_cov

    def get_potential_performance(self, orders):
        """
        Calculates the potential performance of the agent based on the given orders.
        """
        self._current_holdings_info()
        holdings = self._current_holdings
        cash = self._cash

        for order in orders:
            if order.order_side == OrderSide.SELL:
                holdings[order.market.fm_id] += order.units
                cash -= order.price * order.units
            else:
                holdings[order.market.fm_id] -= order.units
                cash += order.price * order.units
        potential_performance = self._calculate_performance(cash, holdings)
        return potential_performance

    def _calculate_performance(self, cash, holdings):
        """
        Calculates the performance of the agent based on the cash and holdings.

        Parameters:
        - cash (float): Current cash amount
        - holdings (dict): Current holdings of the agent

        Returns:
        - performance (float): Performance based on the cash and holdings
        """
        b = self._risk_penalty
        expected_payoff = in_dollar(cash)
        payoff_variance = self._payoff_variance_covariance(holdings)
        for market_id in self._current_holdings:
            expected_payoff += in_dollar(
                self._expected_return(self._market_ids[
                    market_id].item)) * holdings[market_id]
        performance = expected_payoff - b * payoff_variance
        return performance

    def _most_optimal_performance(self):
        """
        From all possible combinations of orders,
        retain the best combination and return performance score
        """
        performance_score = 0
        for combination in self._possible_combinations():
            if self.get_potential_performance(combination) > \
                    self._current_performance and \
                    self._list_order_valid(combination):
                performance_score = self.get_potential_performance(combination)
                self._combination = combination
        return performance_score

    def is_portfolio_optimal(self):
        """
        Returns true if the current holdings are optimal
        (as per the performance formula), false otherwise.
        """
        self._current_holdings_info()
        perf1 = self._calculate_performance(self._cash, self._current_holdings)
        if self._most_optimal_performance() > perf1:
            return False
        return True

    def order_accepted(self, order):
        """
        Handles the event when an order is accepted.
        """
        self.inform("Order Accepted: " + str(order))

        if self._list_used_up:
            self._waiting_for_server = False
            self._list_used_up = False
        self._waiting_for_mm = False

    def order_rejected(self, info, order):
        """
        Handles the event when an order is rejected.
        """
        self._waiting_for_server = False

    def _possible_combinations(self):
        """
        Returns all valid possible combinations of orders for potential 
        improvement of performance.

        Returns:
        - possible_combinations (list): List of possible combinations of orders
        """
        possible_combinations = []
        self._bid_ask_info_dict_to_list()
        combine_bid_ask = list(self._best_ask) + list(self._best_bid)

        for one_combination in combine_bid_ask:
            possible_combinations.append([one_combination])

        for i in range(2, self._num_states + 1):
            for combination in list(combinations(combine_bid_ask, i)):
                markets_overlap = 0
                for j in range(len(combination)):
                    for k in range(len(combination)):
                        if j != k:
                            if combination[j].market.fm_id == combination[k].market.fm_id:
                                markets_overlap = 1
                if not markets_overlap:
                    possible_combinations.append(combination)
        return possible_combinations

    def _bid_ask_info_dict_to_list(self):
        """
        Converts the bid and ask information from dictionaries to sorted lists.

        Use this function if you want a list instead of a dictionary.
        The resulting lists are sorted lists of bid and ask.
        """
        self._get_bid_ask_info()
        temporary_best_ask_list = []
        temporary_best_bid_list = []
        best_ask_list = []
        best_bid_list = []

        for best_ask in self._best_ask.items():
            if best_ask is not None:
                temporary_best_ask_list.append(best_ask)

        temporary_best_ask_list = sorted(temporary_best_ask_list)

        for i in range(len(temporary_best_ask_list)):
            best_ask_list.append(temporary_best_ask_list[i][1])

        for best_bid in self._best_bid.items():
            if best_bid is not None:
                temporary_best_bid_list.append(best_bid)

        temporary_best_bid_list = sorted(temporary_best_bid_list)

        for i in range(len(temporary_best_bid_list)):
            best_bid_list.append(temporary_best_bid_list[i][1])

        self._best_ask = best_ask_list
        self._best_bid = best_bid_list

    def _get_bid_ask_info(self):
        """
        Retrieves the best bid & ask information and stores it in dictionaries.

        The best bid information is stored in self._best_bid dictionary,
        and the best ask information is stored in self._best_ask dictionary.
        """
        self._best_bid = {}
        self._best_ask = {}

        current_order_list = Order.current().items()

        for order_num, order in current_order_list:
            if order.order_side == OrderSide.BUY and not order.mine:
                if order.fm_id not in self._best_bid:
                    copy_order = copy.copy(order)
                    copy_order.units = 1
                    self._best_bid[order.market.fm_id] = copy_order
                else:
                    if order.price > self._best_bid[order.fm_id].price:
                        copy_order = copy.copy(order)
                        copy_order.units = 1
                        self._best_bid[order.market.fm_id] = copy_order
            elif order.order_side == OrderSide.SELL and not order.mine:
                if order.fm_id not in self._best_ask:
                    copy_order = copy.copy(order)
                    copy_order.units = 1
                    self._best_ask[order.market.fm_id] = copy_order
                else:
                    if order.price < self._best_ask[order.fm_id].price:
                        copy_order = copy.copy(order)
                        copy_order.units = 1
                        self._best_ask[order.market.fm_id] = copy_order

    def received_orders(self, orders: List[Order]):
        """
        If improving performance is possible, perform the trades
        If market maker conditions are valid, perform trades based on its role
        Market maker conditions are when session is in last 5 minutes and
        reactive bots have not been sending orders for 10 seconds
        """
        combination = []
        make_order_list = []

        # Accounting for market maker bots
        if self._mm_condition_1 and self._mm_condition_2 and \
                self._if_no_pending_order():
            self._market_maker_order()

        if not self.is_portfolio_optimal():
            combination = self._combination
            self.inform("Make portfolio optimal by trading combination: "
                        + str(combination))
            not_optimal = True
        else:
            not_optimal = False

        if not_optimal:
            if not self._waiting_for_server and self._if_no_pending_order():
                for order in combination:
                    make_order = copy.copy(order)
                    if order.order_side == OrderSide.BUY:
                        make_order.order_side = OrderSide.SELL
                    elif order.order_side == OrderSide.SELL:
                        make_order.order_side = OrderSide.BUY
                    make_order.units = 1
                    make_order_list.append(make_order)
                self._send_order_list(make_order_list)

    def _market_maker_order(self):
        """
        Bot can perform market maker order in the last 5 minutes
        provided that it has not done reactive order in the previous 20 seconds
        """
        self.inform("Market Maker Activated")

        best_bid = {}
        best_ask = {}
        current_order_list = Order.current().items()
        for order_num, current_order in current_order_list:
            if current_order.order_side == OrderSide.BUY:
                if current_order.fm_id not in best_bid:
                    copy_order = copy.copy(current_order)
                    copy_order.units = 1
                    best_bid[current_order.market.fm_id] = copy_order
                else:
                    if current_order.price > \
                            best_bid[current_order.fm_id].price:
                        copy_order = copy.copy(current_order)
                        copy_order.units = 1
                        best_bid[current_order.market.fm_id] = copy_order
            elif current_order.order_side == OrderSide.SELL:
                if current_order.fm_id not in best_ask:
                    copy_order = copy.copy(current_order)
                    copy_order.units = 1
                    best_ask[current_order.market.fm_id] = copy_order
                else:
                    if current_order.price < \
                            best_ask[current_order.fm_id].price:
                        copy_order = copy.copy(current_order)
                        copy_order.units = 1
                        best_ask[current_order.market.fm_id] = copy_order

        first_market = list(self._market_ids.keys())[0]
        tick = self._market_ids[first_market].price_tick
        minimum = self._market_ids[first_market].min_price
        maximum = self._market_ids[first_market].max_price

        order_list = []

        for market_id in self._current_holdings:

            appended = False
            sell_preferred = randint(0, 1)

            if sell_preferred:
                for price in range(best_bid[market_id].price if
                                   market_id in best_bid else minimum + 1,
                                   best_ask[market_id].price if
                                   market_id in best_ask else maximum - 1,
                                   tick):
                    order = Order.create_new()
                    order.price = price
                    order.units = 1
                    order.order_type = OrderType.LIMIT
                    order.order_side = OrderSide.BUY
                    order.market = Market(market_id)
                    if self._order_valid(order) and \
                            self.get_potential_performance([order]) > \
                            self._current_performance and \
                            not self._waiting_for_mm:
                        order.order_side = OrderSide.SELL
                        order_list.append(order)
                        appended = True
                        break

                if not appended:
                    for price in range(best_ask[market_id].price if
                                       market_id in best_ask else maximum - 1,
                                       best_bid[market_id].price if
                                       market_id in best_bid else minimum + 1,
                                       -tick):
                        order = Order.create_new()
                        order.price = price
                        order.units = 1
                        order.order_type = OrderType.LIMIT
                        order.order_side = OrderSide.SELL
                        order.market = Market(market_id)
                        if self._order_valid(order) and \
                                self.get_potential_performance([order]) > \
                                self._current_performance and \
                                not self._waiting_for_mm:
                            order.order_side = OrderSide.BUY
                            order_list.append(order)
                            break

            if not sell_preferred:
                for price in range(best_ask[market_id].price if
                                   market_id in best_ask else maximum - 1,
                                   best_bid[market_id].price if
                                   market_id in best_bid else minimum + 1,
                                   -tick):
                    order = Order.create_new()
                    order.price = price
                    order.units = 1
                    order.order_type = OrderType.LIMIT
                    order.order_side = OrderSide.SELL
                    order.market = Market(market_id)
                    if self._order_valid(order) and \
                            self.get_potential_performance([order]) > \
                            self._current_performance and \
                            not self._waiting_for_mm:
                        order.order_side = OrderSide.BUY
                        order_list.append(order)
                        appended = True
                        break
                if not appended:
                    for price in range(best_bid[market_id].price if
                                       market_id in best_bid else minimum + 1,
                                       best_ask[market_id].price if
                                       market_id in best_ask else maximum - 1,
                                       tick):
                        order = Order.create_new()
                        order.price = price
                        order.units = 1
                        order.order_type = OrderType.LIMIT
                        order.order_side = OrderSide.BUY
                        order.market = Market(market_id)
                        if self._order_valid(order) and \
                                self.get_potential_performance([order]) > \
                                self._current_performance and \
                                not self._waiting_for_mm:
                            order.order_side = OrderSide.SELL
                            order_list.append(order)
                            break

        self._send_order_list(order_list)
        self._time_last_order_sent = time.time()

    def _if_no_pending_order(self):
        """
        Checks if there are any pending orders placed by the agent.

        Returns:
            bool: True if there are no pending orders, False otherwise.
        """
        current_order_list = Order.current().items()
        for order_id, order in current_order_list:
            if order.mine and order.is_pending:
                self.inform("Status: Order is Pending")
                return False
        return True

    def _send_order_list(self, order_list):
        """
        Sends a list of valid orders to the market.

        Args:
            order_list (List[Order]): List of orders to be sent.

        The function sends each order in the order_list that has 
        not been processed before.
        After sending the orders, it sets the waiting flag for server 
        response and marks the list as used up.
        """
        self.inform("Order List: " + str(order_list))
        for order in order_list:
            if order not in self._processed_list:
                self._send_valid_order(order)
                self._processed_list.append(order)
        self._waiting_for_server = True
        self._list_used_up = True

    def _send_valid_order(self, order_to_send):
        """
        Sends a valid order to the market.

        Args:
            order_to_send (Order): Order to be sent.

        Checks if the order can be sent based on available cash or units.
        If the order meets the criteria, it is sent using the send_order method,
        and the last order sent time is updated.
        """
    


    def _order_valid(self, order):
        """
        Checks if a single order is valid.
        """
        cash = self._cash
        units_available = self._current_units_available

        price = order.price
        order_side = order.order_side
        order_fm_id = order.market.fm_id
        order_units = order.units

        if order_side == OrderSide.BUY:
            cash -= price
        elif order_side == OrderSide.SELL:
            units_available[order_fm_id] -= order_units

        if cash < 0:
            return False
        if units_available[order_fm_id] < 0:
            return False
        return True

    def _list_order_valid(self, potential_orders):
        """
        Checks if a list of potential orders is valid.
        """
        if not potential_orders:
            return False

        cash = self._cash
        units_available = self._current_units_available

        for order in potential_orders:
            price = order.price
            order_side = order.order_side
            order_fm_id = order.market.fm_id
            order_units = order.units

            if order_side == OrderSide.BUY:
                units_available[order_fm_id] -= order_units
            elif order_side == OrderSide.SELL:
                cash -= price

        if cash < 0:
            return False
        for market_id in units_available:
            if units_available[market_id] < 0:
                return False
        return True

    def received_session_info(self, session: Session):
        """
        Callback function invoked when session information is received.
        Updates the session open flag and starts the timer for tracking 
        session time.
        """
        if session.is_open:
            self._session_open = True
        self._time_start = time.time()

    def pre_start_tasks(self):
        """
        Bot checks if there is idle public order that is from user.
        Check this so that there is no partially filled order due to
        potential server issue or time lag
        Set specified second in global variable IDLE_CHECK_TIME
        """
        threading.Timer(IDLE_CHECK_TIME, self.pre_start_tasks).start()
        if self._session_open:
            self._order_idle_check()
        # Toggle
        self._waiting_for_server = False
        self._list_used_up = False

    def _order_idle_check(self):
        """
        Cancels an existing pending order if there is so that I
        can make a better order based on updated environment
        """
        current_order_list = Order.current().items()
        for order_num, order in current_order_list:
            if order.is_pending and order.mine:
                cancel_order = copy.copy(order)
                cancel_order.order_type = OrderType.CANCEL
                self.send_order(cancel_order)
                self.inform("Order is idle, cancelling order.")

    def _current_holdings_info(self):
        """
        Update current holdings
        """
        for key, value in self.holdings.assets.items():
            self._current_holdings[value.market.fm_id] = value.units
            self._current_holdings_item[value.market.item] = value.units
            self._current_units_available[value.market.fm_id] = \
                value.units_available

def received_holdings(self, holdings):
    """
    Callback function invoked when holdings information is received.
    
    Updates the agent's cash, cash available, current holdings, units 
    available, variance, covariance, payoff variance, current performance, 
    and tracks time conditions.
    """
    self._cash = holdings.cash
    self._cash_available = holdings.cash_available

    self._current_holdings_info()
    self.inform("Current cash: " + str(self._cash))
    self.inform("Current holdings: " + str(self._current_holdings_item))
    self.inform("Current units: " + str(self._current_units_available))

    self._make_variance()
    self._make_covariance()

    self.inform("Current payoff variance: " +
                str(self._payoff_variance_covariance(self._current_holdings)))
    self.inform("Current performance: " +
                str(round(self._calculate_performance(
                    self._cash, self._current_holdings), 3)))
    self._current_performance = self._calculate_performance(
        self._cash, self._current_holdings)

    time_elapsed = time.time() - self._time_start
    if time_elapsed > self._time_condition_mm:
        self._mm_condition_1 = 1
    if self._time_last_order_sent > 0:
        if time.time() - self._time_last_order_sent > 1:
            self._mm_condition_2 = 1
        else:
            self._mm_condition_2 = 0
    self.inform("Time elapsed: " + str(round(time_elapsed, 3)))
    if self._time_last_order_sent > 0:
        self.inform("Time since last order sent " +
                    str(round(time.time() - self._time_last_order_sent, 3)))



if __name__ == "__main__":
    FM_ACCOUNT = "ardent-founder"
    FM_EMAIL = "sungp2@student.unimelb.edu.au"
    FM_PASSWORD = "******"
    MARKETPLACE_ID = 1054

    bot = CAPMBot(FM_ACCOUNT, FM_EMAIL, FM_PASSWORD, MARKETPLACE_ID)
    bot.run()