# CAPMBot Description

## Overview
CAPMBot is a trading bot that implements the Capital Asset Pricing Model (CAPM) to make optimal investment decisions based on market conditions.

The bot acts as both a reactive bot and a market maker bot, depending on the conditions in the market. It optimizes the portfolio when the current portfolio is not optimal and makes market-making orders based on certain conditions.

## Features
1. Optimal Portfolio Management: The bot analyzes market conditions and optimizes the portfolio based on the CAPM model.

2. Market Making: The bot can act as a market maker in the last 5 minutes of a session, provided that it has not done a reactive order in the previous 20 seconds.

3. Order Handling: The bot checks for the validity of each order before placing it. It also checks if there are any pending orders.

4. Session Management: The bot receives session information and performs tasks based on whether the session is open.

5. Pre-Start Tasks: The bot checks if there is an idle public order from the user and cancels it if found.

6. Holdings Management: The bot receives holdings information and updates the agent's cash, cash available, current holdings, units available, variance, covariance, payoff variance, and current performance.

## Usage
To use the bot, you need to have access to fmmarket and a valid account. Replace the placeholders in the following code with your own credentials:

```python
if __name__ == "__main__":
    FM_ACCOUNT = "your-account"
    FM_EMAIL = "your-email"
    FM_PASSWORD = "your-password"
    MARKETPLACE_ID = your-marketplace-id

    bot = CAPMBot(FM_ACCOUNT, FM_EMAIL, FM_PASSWORD, MARKETPLACE_ID)
    bot.run()
```

