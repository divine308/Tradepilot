# TradePilot AI

## Autonomous AI Trading Agent

TradePilot AI is an autonomous AI-powered trading platform designed to transform real-time market intelligence into disciplined, executable trading decisions.

Instead of requiring a trader to manually monitor markets, interpret signals, determine risk, place orders, and manage positions, TradePilot brings these processes together through a multi-agent architecture.

The system combines AI reasoning, market data, deterministic risk controls, and Alpaca's trading infrastructure to create an end-to-end autonomous trading workflow.

### Core Pipeline

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

## What TradePilot Does

TradePilot is designed to continuously move through the complete trading lifecycle:

1. Observe market conditions
2. Analyze available market data
3. Identify potential opportunities
4. Generate a trading decision
5. Evaluate the proposed trade against risk rules
6. Execute approved trades through Alpaca
7. Monitor open positions
8. Apply position-management rules
9. Continue monitoring for new opportunities

The objective is to move beyond AI-powered market analysis and create an autonomous agent capable of reasoning, acting, and managing positions within predefined constraints.

---

# Multi-Agent Architecture

TradePilot uses specialized agents rather than relying on a single AI prompt to make every decision.

## Market Agent

The Market Agent is responsible for understanding current market conditions.

Responsibilities include:

* Retrieving market data
* Processing price information
* Identifying market conditions
* Providing structured market context
* Supplying information required by downstream agents

---

## Strategy Agent

The Strategy Agent interprets market information and generates a potential trading decision.

Possible decisions include:

```text
BUY
SELL
HOLD
```

The strategy layer can also consider potential entry conditions, stop-loss levels, take-profit levels, and other trade parameters.

---

## Risk Agent

The Risk Agent acts as a deterministic safety layer between AI-generated decisions and trade execution.

TradePilot currently incorporates predefined controls including:

* Maximum 5% account-equity allocation per trade
* Maximum 50% portfolio exposure
* Position sizing constraints
* Trade validation before execution
* Position protection mechanisms

The purpose of this layer is to prevent an AI-generated decision from automatically becoming an unrestricted trade.

---

## Supervisor Agent

The Supervisor coordinates the overall decision-making process.

It helps ensure that:

```text
Market Analysis
      ↓
Strategy Decision
      ↓
Risk Evaluation
      ↓
Execution Decision
```

happens in the correct order.

The Supervisor provides an additional coordination layer between the specialized agents and execution system.

---

## Autonomous Agent

The Autonomous Agent coordinates the continuous trading workflow.

Rather than treating every request as an isolated AI interaction, TradePilot is designed around an ongoing observe → analyze → decide → execute → monitor cycle.

This allows the system to operate as an autonomous trading workflow rather than simply functioning as a market-analysis chatbot.

---

# Risk-Aware Autonomous Execution

One of the core principles behind TradePilot is that AI should not have unrestricted control over trading execution.

The architecture separates AI reasoning from deterministic risk enforcement.

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

This means an AI-generated trading decision must satisfy predefined risk constraints before reaching the execution layer.

---

# Position Management

Once a position is opened, TradePilot can apply automated position-management logic.

Depending on the strategy and configuration, this can include:

* Stop-loss protection
* Take-profit protection
* Breakeven protection
* Position monitoring
* Order-state monitoring
* Exposure monitoring

The goal is to ensure that TradePilot does not simply open positions and forget about them.

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

This allows TradePilot to connect AI decision-making directly to brokerage infrastructure.

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

TradePilot is not designed around a simple prompt such as:

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

This architecture separates market analysis, strategy generation, risk management, and execution into distinct responsibilities.

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

The dashboard is designed to provide visibility into the autonomous trading system.

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

# API

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

The project explores how autonomous AI agents can be connected to real trading infrastructure while maintaining deterministic risk controls.

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

TradePilot combines several capabilities that are often implemented separately:

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

# Safety and Risk Disclaimer

TradePilot is an experimental autonomous trading system built for research, development, testing, and demonstration purposes.

Automated trading involves substantial financial risk. AI-generated decisions can be incorrect, market conditions can change rapidly, and past performance does not guarantee future results.

Users should thoroughly test strategies using paper trading and understand the risks involved before considering live deployment.

---

# Team

TradePilot AI was built by the TradePilot team.

### Contributors

* Divine Okechukwu - Full Stack Dev, Al/Ml
* Esther Olinya - Data Analyst
* Peace SOSSA - Researcher
* Jethro Ibebuike - AI Logic Engineer

---

# Built With

React
FastAPI
OpenAI
Alpaca
SQLAlchemy
Vite
Vercel
GitHub

---

## TradePilot AI

**Observe. Reason. Execute. Manage.**
