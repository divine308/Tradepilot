# TradePilot AI

## Autonomous AI Trading Agent

TradePilot AI is an autonomous AI-powered trading platform designed to turn real-time market data into disciplined, executable trading decisions.

Instead of requiring a trader to manually monitor markets, interpret signals, determine risk, place orders, and manage positions, TradePilot brings these processes together through a multi-agent architecture.

The system combines AI reasoning, market data, deterministic risk controls, and Alpaca's trading infrastructure to create an end-to-end autonomous trading workflow.

---

## Core Pipeline

```text
Market Data
     ↓
Market Agent
     ↓
AI Market Analysis
     ↓
Strategy Agent
     ↓
BUY / SELL / HOLD
     ↓
Risk Agent
     ↓
Risk Validation
     ↓
Supervisor Agent
     ↓
Alpaca Execution
     ↓
Position Management
     ↓
Continuous Monitoring
```

---

# What TradePilot Does

TradePilot is designed around an autonomous trading workflow that moves through the complete trading lifecycle:

1. Observe market conditions
2. Analyze available market data
3. Identify potential opportunities
4. Generate a trading decision
5. Evaluate the proposed trade against predefined risk rules
6. Execute approved trades through Alpaca
7. Monitor open positions
8. Apply position-management rules
9. Continue monitoring for new opportunities

The goal is to move beyond AI-powered market analysis and build a system capable of reasoning, acting, and managing positions within clearly defined constraints.

---

# Multi-Agent Architecture

TradePilot uses specialized agents rather than relying on a single AI prompt to handle the entire trading process.

## Market Agent

The Market Agent is responsible for collecting and structuring market information for the rest of the system.

Responsibilities include:

* Retrieving market data
* Processing price information
* Identifying relevant market conditions
* Building structured market context
* Supplying information to downstream agents

---

## Strategy Agent

The Strategy Agent interprets the available market context and generates a potential trading decision.

Possible decisions include:

```text
BUY
SELL
HOLD
```

Depending on the strategy and market conditions, the strategy layer can also generate parameters such as potential entry levels, stop-loss levels, take-profit levels, and position sizing considerations.

---

## Risk Agent

The Risk Agent provides a deterministic safety layer between AI-generated decisions and trade execution.

TradePilot currently incorporates predefined controls including:

* Maximum 5% account-equity allocation per trade
* Maximum 50% portfolio exposure
* Position sizing constraints
* Trade validation before execution
* Position protection mechanisms

The purpose of this layer is to prevent an AI-generated decision from automatically becoming an unrestricted trade.

---

## Supervisor Agent

The Supervisor coordinates the major stages of the trading workflow.

```text
Market Analysis
      ↓
Strategy Decision
      ↓
Risk Evaluation
      ↓
Execution Decision
```

This coordination layer helps ensure that specialized agents operate in the intended sequence before a trade reaches the execution layer.

---

## Autonomous Agent

The Autonomous Agent coordinates the broader trading workflow.

Rather than treating every interaction as an isolated AI request, TradePilot is designed around an ongoing:

```text
Observe
   ↓
Analyze
   ↓
Decide
   ↓
Validate
   ↓
Execute
   ↓
Monitor
   ↓
Repeat
```

cycle.

This allows TradePilot to function as an autonomous trading workflow rather than simply as a market-analysis chatbot.

---

# Risk-Aware Autonomous Execution

A central principle of TradePilot is that AI should not have unrestricted authority over trading execution.

AI reasoning and deterministic risk enforcement are separated within the architecture.

```text
AI Decision
     ↓
Risk Gate
     ↓
Approved?
   ↙     ↘
 NO       YES
 ↓         ↓
Reject   Execute
           ↓
        Alpaca
```

An AI-generated trading decision must therefore satisfy predefined risk constraints before reaching the execution layer.

This separation is designed to make autonomous execution more controlled and predictable.

---

# Position Management

TradePilot does not treat opening a position as the end of the workflow.

Once a position is opened, the system can apply automated position-management logic, depending on the strategy and configuration.

This includes:

* Stop-loss protection
* Take-profit protection
* Breakeven protection
* Position monitoring
* Order-state monitoring
* Exposure monitoring

The objective is to continuously monitor positions rather than simply generate an entry signal and stop there.

---

# Alpaca Integration

TradePilot uses Alpaca as its trading infrastructure.

The integration provides access to:

* Account information
* Account equity
* Cash
* Buying power
* Positions
* Market data
* Order execution
* Position monitoring

The overall architecture is:

```text
TradePilot AI
     ↓
FastAPI Backend
     ↓
Trading Agents
     ↓
Risk Controls
     ↓
Alpaca API
     ↓
Trading Account
```

---

# AI Decision Architecture

TradePilot is not designed around a single prompt such as:

> "Should I buy this stock?"

Instead, AI reasoning is integrated into a structured decision pipeline.

```text
Market Data
     ↓
Market Context
     ↓
AI Analysis
     ↓
Strategy Decision
     ↓
Risk Validation
     ↓
Execution
```

This separates market analysis, strategy generation, risk management, coordination, and execution into distinct responsibilities.

---

# Backend Architecture

TradePilot's backend is built with Python and FastAPI.

```text
React / Vite Frontend
          ↓
       REST API
          ↓
     FastAPI Backend
          ↓
   ┌──────┼───────┐
   ↓      ↓       ↓
 Alpaca   AI    Database
   ↓      ↓
Trading  Agents
          ↓
   Risk / Strategy
          ↓
       Execution
```

### Backend Technologies

* Python
* FastAPI
* Uvicorn
* SQLAlchemy
* REST APIs
* Alpaca API
* OpenAI API

---

# Frontend

TradePilot provides a web-based trading interface built with React and Vite.

The dashboard provides visibility into the trading system, account state, market information, positions, and AI-powered functionality.

### Frontend capabilities include:

* Account overview
* Portfolio information
* Account equity
* Cash and buying power
* Open positions
* Market data
* Live market charts
* Trading activity
* Autonomous trading functionality
* AI-powered market analysis
* Risk monitoring

---

# REST API

TradePilot exposes REST endpoints through its FastAPI backend.

Examples include:

```text
GET /api/trading/account
GET /api/trading/positions
GET /api/market/bars
```

These endpoints allow the frontend and trading services to communicate with the backend.

The backend then communicates with external services such as Alpaca and OpenAI.

---

# Technology Stack

## Frontend

* React
* Vite
* Axios
* Lucide React

## Backend

* Python
* FastAPI
* Uvicorn
* SQLAlchemy

## Artificial Intelligence

* OpenAI API
* Multi-agent architecture

## Trading Infrastructure

* Alpaca API
* Alpaca Market Data
* Alpaca Trading API

## Deployment

* Vercel
* GitHub
* Render

---

# Repository Structure

TradePilot is separated into frontend and backend repositories.

### Frontend

https://github.com/divine308/TradepilotAi

### Backend

https://github.com/divine308/Tradepilot

The backend repository contains the API, trading services, agents, configuration, and application runtime.

---

# Live Demo

Try TradePilot AI:

https://tradepilot-ai-dun.vercel.app/

---

# Hackathon Submission

TradePilot AI was built for the lablab.ai Alpaca AI Trading Agents Hackathon.

The project was submitted to the **Options Alpha Agents** event track.

TradePilot's current implementation focuses on autonomous trading workflows, AI-driven market analysis, deterministic risk controls, Alpaca execution, and position management.

The project explores how autonomous AI agents can interact with trading infrastructure while operating within predefined safety constraints.

### Submission

https://lablab.ai/submissions/tpyjss8emfl37zk4jq9jz16t

---

# Project Philosophy

TradePilot is built around a simple idea:

**AI should not just analyze markets. It should be able to observe, reason, act, and manage the consequences of its actions within clearly defined boundaries.**

Traditional trading workflows often require humans to manually perform multiple steps:

```text
Monitor Market
     ↓
Analyze
     ↓
Create Strategy
     ↓
Evaluate Risk
     ↓
Place Order
     ↓
Monitor Position
     ↓
Manage Exit
```

TradePilot attempts to bring these processes together into an autonomous system:

```text
Observe
   ↓
Reason
   ↓
Decide
   ↓
Validate
   ↓
Execute
   ↓
Manage
   ↓
Repeat
```

---

# Why TradePilot?

TradePilot combines capabilities that are often implemented separately:

* AI market analysis
* Multi-agent decision making
* Deterministic risk controls
* Automated execution
* Portfolio awareness
* Position management
* Real-time market information
* Brokerage integration

The result is an architecture designed around autonomous, risk-aware trading rather than simply generating trading predictions.

---

# Performance & Validation

TradePilot has been tested through paper-trading workflows during development and iteration.

The system has been refined through testing of:

* Trading strategies
* Risk controls
* Order execution
* Position management
* Market-data handling
* Autonomous trading workflows

Performance results from paper trading should not be interpreted as evidence of guaranteed future returns or live-market performance.

Formal historical backtesting and independent validation remain areas for further development.

---

# Safety and Risk Disclaimer

TradePilot is an experimental autonomous trading system built for research, development, testing, and demonstration purposes.

Automated trading involves substantial financial risk. AI-generated decisions can be incorrect, market conditions can change rapidly, and past performance does not guarantee future results.

Users should thoroughly test strategies using paper trading and understand the risks involved before considering live deployment.

---

# Team

TradePilot AI was built by the TradePilot team.

### Contributors

* **Divine Okechukwu** — Full Stack Developer, AI/ML
* **Esther Olinya** — Data Analyst
* **Peace SOSSA** — Researcher
* **Jethro Ibebuike** — AI Logic Engineer

---

# Built With

React · FastAPI · OpenAI · Alpaca · SQLAlchemy · Vite · Vercel · GitHub

---

## TradePilot AI

**Observe. Reason. Execute. Manage.**
