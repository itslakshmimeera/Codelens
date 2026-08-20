# CodeLens


> **AI-Powered Codebase Intelligence Platform**


CodeLens is an AI-powered codebase intelligence platform designed to help developers understand, search, analyze, and reason about large software repositories.


Instead of treating a codebase as a collection of independent files, CodeLens builds a structured understanding of the repository by combining source-code parsing, Abstract Syntax Trees (ASTs), symbol extraction, dependency graphs, semantic search, Retrieval-Augmented Generation (RAG), and Large Language Models (LLMs).


The goal is to allow developers to ask questions such as:


- "What does this function do?"
- "Where is user authentication implemented?"
- "What files depend on this class?"
- "If I change this function, what could break?"
- "How does data flow through this feature?"
- "Find the code responsible for processing payments."
- "Explain how this module interacts with the rest of the application."
- "Generate tests for this function."


---


## 🚧 Current Status


CodeLens is currently in:


### Phase 1 — Application Foundation


The current implementation establishes the basic full-stack architecture:


- FastAPI backend
- React + TypeScript + Vite frontend
- Backend health-check API
- Frontend-to-backend communication
- Basic backend tests
- Environment configuration templates
- Git-safe project configuration


The advanced code-intelligence and AI components will be implemented incrementally in later phases.


---


# 🎯 Problem Statement


Modern software repositories can contain thousands of files, classes, functions, dependencies, and configuration files.


Understanding an unfamiliar codebase often requires developers to:


1. Manually search through files.
2. Follow function calls across multiple modules.
3. Understand dependencies between components.
4. Trace how data flows through the system.
5. Determine which parts of the application may be affected by a change.
6. Read large amounts of documentation and source code.
7. Repeatedly switch between files and tools.


Traditional text-based search can find matching words, but it does not truly understand the structure and relationships within a codebase.


CodeLens aims to solve this by building a machine-readable representation of the repository and combining structural code analysis with semantic retrieval and AI reasoning.


---


# 💡 What CodeLens Does


The long-term CodeLens workflow is:


```text
GitHub Repository
       │
       ▼
Repository Ingestion
       │
       ▼
Source Code Parsing
       │
       ▼
AST / Symbol Extraction
       │
       ▼
Dependency Graph
       │
       ▼
Code Chunking
       │
       ▼
Embeddings
       │
       ▼
Semantic Retrieval
       │
       ▼
RAG Pipeline
       │
       ▼
LLM Reasoning
       │
       ├───────────────┬────────────────┐
       ▼               ▼                ▼
   Code Q&A      Impact Analysis   Test Generation

This architecture will allow CodeLens to reason about both:

What the code means
How the code is structurally connected
🏗️ Architecture

The planned system consists of several major layers.

                    ┌───────────────────────┐
                    │       React UI        │
                    │   TypeScript + Vite   │
                    └───────────┬───────────┘
                                │
                                │ HTTP / REST
                                ▼
                    ┌───────────────────────┐
                    │      FastAPI API      │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                 │
              ▼                 ▼                 ▼
       Repository          Code Analysis      AI Services
        Services             Services
              │                 │                 │
              ▼                 ▼                 ▼
          GitHub API       AST / Symbols      Retrieval
                              │                 │
                              ▼                 ▼
                        Dependency Graph       RAG
                                                │
                                                ▼
                                               LLM
              │                 │                 │
              └─────────────────┼─────────────────┘
                                ▼
                         PostgreSQL
🧩 Core Modules

The planned CodeLens system will contain the following major modules.

1. Repository Ingestion

Responsible for obtaining source code from GitHub repositories.

Responsibilities include:

Connecting to GitHub.
Cloning repositories.
Tracking repository metadata.
Detecting branches and commits.
Reading source files.
Ignoring unnecessary files such as build artifacts and dependencies.
2. Code Parser

The parser analyzes source files and converts source code into structured representations.

The system will support programming languages incrementally.

The parser will identify:

Files
Classes
Functions
Methods
Variables
Imports
Exports
Interfaces
Modules
Calls
Inheritance relationships
3. AST Analysis

AST stands for:

Abstract Syntax Tree

An AST represents source code as a structured tree.

For example:

def add(a, b):
    return a + b

can conceptually be represented as:

FunctionDef
│
├── name: add
│
├── arguments
│   ├── a
│   └── b
│
└── Return
    └── BinaryOperation
        ├── a
        ├── +
        └── b

AST analysis allows CodeLens to understand the structure of code rather than treating it as plain text.

🔗 4. Symbol Extraction

CodeLens will extract important code entities called symbols.

Examples:

Class
Function
Method
Variable
Interface
Module

Each symbol can contain metadata such as:

name
type
file
line_start
line_end
parent
language
signature

For example:

Symbol
--------------------------
name: calculate_total
type: function
file: services/payment.py
line_start: 42
line_end: 67
🕸️ 5. Dependency Analysis

CodeLens will build relationships between symbols and files.

For example:

UserService
     │
     ├── uses → UserRepository
     │
     └── uses → AuthenticationService
                       │
                       └── uses → TokenManager

These relationships form a dependency graph.

The graph can answer questions such as:

What does this function depend on?
What depends on this class?
Which modules use this service?
What happens if this function changes?
📦 6. Code Chunking

Large source files cannot always be sent directly to an LLM.

CodeLens will therefore divide source code into meaningful chunks.

Instead of blindly splitting every 500 characters, chunks can be based on code structures such as:

Class
Function
Method
Module
Logical section

Each chunk retains metadata such as:

file
language
symbol
line range
repository
commit
🧠 7. Embeddings

Embeddings convert code or text into numerical vectors.

Conceptually:

Source Code
     │
     ▼
Embedding Model
     │
     ▼
[0.12, -0.42, 0.87, ...]

Similar concepts produce vectors that are close together in vector space.

For example:

"authentication logic"

may retrieve code containing:

login()
verify_token()
authenticate_user()

even if the exact phrase "authentication logic" never appears in the source code.

🔎 8. Semantic Retrieval

Semantic retrieval finds the most relevant pieces of code for a user's question.

For example:

User:
"Where is password validation implemented?"

The retrieval system searches the indexed code and may return:

auth/service.py
auth/validators.py
models/user.py

The retrieved code becomes context for the AI system.

📚 9. RAG

RAG stands for:

Retrieval-Augmented Generation

Instead of asking an LLM to answer questions using only its general knowledge, CodeLens first retrieves relevant information from the actual repository.

The process is:

User Question
      │
      ▼
Query Processing
      │
      ▼
Semantic Retrieval
      │
      ▼
Relevant Code Chunks
      │
      ▼
Context Construction
      │
      ▼
LLM
      │
      ▼
Answer

This helps the LLM answer questions using the user's actual codebase.

🤖 10. LLM Code Reasoning

The LLM will receive:

User question
Relevant source code
Symbol information
Dependency information
Repository metadata

It can then generate explanations based on the retrieved repository context.

Example:

User:
"How does authentication work?"

CodeLens could retrieve:

routes/auth.py
services/auth_service.py
services/token_service.py
models/user.py

The LLM can then explain the authentication flow using those files.

💥 11. Impact Analysis

One of the major features of CodeLens will be change-impact analysis.

Suppose a developer changes:

calculate_price()

CodeLens can analyze:

calculate_price()
       │
       ├── called by → CheckoutService
       │                   │
       │                   └── called by → CheckoutController
       │
       └── called by → InvoiceService

The system can identify potentially affected components.

The result might look like:

Potentially affected files:


1. checkout/service.py
2. checkout/controller.py
3. invoice/service.py
4. tests/test_checkout.py

This helps developers understand the consequences of a change before modifying the code.

🧪 12. Automated Test Generation

CodeLens will eventually generate test cases based on:

Function signatures
Existing implementation
Dependencies
Existing tests
Edge cases
Repository conventions

For example:

def divide(a, b):
    return a / b

CodeLens could identify cases such as:

1. Normal division
2. Division by zero
3. Negative numbers
4. Floating-point values

and generate appropriate tests.

🗄️ Database

The planned database layer will use PostgreSQL.

PostgreSQL will store structured information such as:

Repositories
Files
Code Symbols
Code Chunks
Dependencies
Queries
Analysis Results

Vector storage may also be added for embedding-based retrieval.

🔄 Data Flow

The complete planned data flow is:

1. User connects a GitHub repository
                 │
                 ▼
2. CodeLens clones / reads repository
                 │
                 ▼
3. Source files are discovered
                 │
                 ▼
4. Files are parsed
                 │
                 ▼
5. ASTs are generated
                 │
                 ▼
6. Symbols are extracted
                 │
                 ▼
7. Dependencies are identified
                 │
                 ▼
8. Code is divided into semantic chunks
                 │
                 ▼
9. Chunks are embedded
                 │
                 ▼
10. Embeddings are indexed
                 │
                 ▼
11. User asks a question
                 │
                 ▼
12. Query is embedded
                 │
                 ▼
13. Relevant code is retrieved
                 │
                 ▼
14. Dependency information is added
                 │
                 ▼
15. Context is sent to the LLM
                 │
                 ▼
16. LLM generates an answer
                 │
                 ▼
17. Answer is displayed in the UI
🛠️ Technology Stack
Frontend
React

Used to build the CodeLens user interface.

React allows the application to be divided into reusable components.

TypeScript

TypeScript provides static typing for the frontend.

This helps reduce errors and makes the application easier to maintain as it grows.

Vite

Vite provides:

Fast development server
Fast builds
React integration
Modern frontend tooling
Backend
Python

Python is used for backend development because CodeLens relies heavily on:

Code parsing
AST processing
Machine learning
Embeddings
AI libraries
Data processing

Python has a strong ecosystem for all of these areas.

FastAPI

FastAPI is used to build the backend API.

It provides:

High-performance APIs
Automatic API documentation
Type validation
Async support
Easy integration with Python services
Database
PostgreSQL

PostgreSQL will be used as the primary relational database.

It is suitable for storing structured repository metadata and relationships.

Potential future use includes:

Repository metadata
Files
Symbols
Dependencies
Code chunks
Analysis results
Embeddings through vector extensions
Code Parsing
Tree-sitter / AST Tools

Tree-sitter or similar parsing technology will be used to analyze source code structurally.

This allows CodeLens to work with multiple programming languages while preserving code structure.

AI / Retrieval
Embedding Models

Embedding models will convert code and natural-language queries into vector representations.

These vectors enable semantic retrieval.

Vector Search

Vector search will identify code chunks that are semantically related to a user's question.

RAG

RAG connects retrieval with LLM generation.

This allows the model to answer questions using the actual repository as context.

LLM

An LLM will be used for:

Code explanation
Question answering
Reasoning
Impact analysis summaries
Test generation
🧪 Testing Strategy

CodeLens will use multiple levels of testing.

Unit Tests

Test individual functions and services.

Example:

test_health.py
test_parser.py
test_chunker.py
test_retrieval.py
Integration Tests

Test communication between components.

Examples:

Frontend → Backend
Backend → Database
Repository → Parser
Retriever → LLM
End-to-End Tests

Test complete user workflows.

Example:

Connect Repository
       ↓
Index Repository
       ↓
Ask Question
       ↓
Retrieve Code
       ↓
Generate Answer
📁 Current Project Structure

The current Phase 1 structure is:

CodeLens/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   └── main.py
│   │
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_health.py
│   │
│   ├── requirements.txt
│   └── .env.example
│
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── ...
│   │
│   ├── .env.example
│   ├── index.html
│   ├── package.json
│   ├── package-lock.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   └── vite.config.ts
│
├── .gitignore
└── README.md
🚀 Running the Project
Prerequisites

Install:

Python 3.10+
Node.js 18+
npm
Git
Backend Setup

From the project root:

pip install -r backend/requirements.txt

Start the FastAPI server:

uvicorn app.main:app --reload --port 8000

The backend will run at:

http://127.0.0.1:8000

Health endpoint:

http://127.0.0.1:8000/health

Expected response:

{
  "status": "ok"
}
Frontend Setup

Install frontend dependencies:

npm install --prefix frontend

Start the development server:

npm run dev --prefix frontend

The frontend will normally be available at:

http://localhost:5173

The frontend communicates with the FastAPI backend through the /health API.

🧪 Running Tests

Run backend tests with:

python -m pytest backend/tests

The current test suite verifies that the backend health endpoint responds correctly.

🗺️ Development Roadmap
Phase 1 — Application Foundation
 Create FastAPI backend
 Create React + TypeScript + Vite frontend
 Implement /health endpoint
 Connect frontend to backend
 Add basic backend tests
 Add environment templates
 Add Git configuration
Phase 2 — Database Layer

Planned tasks:

 Add PostgreSQL
 Add SQLAlchemy
 Create database configuration
 Create repository model
 Create database migrations
 Add repository metadata storage
 Add database tests
Phase 3 — GitHub Repository Ingestion

Planned tasks:

 Connect GitHub API
 Authenticate GitHub requests
 Clone repositories
 Detect repository branches
 Track commits
 Discover source files
 Ignore unnecessary files
 Store repository metadata
Phase 4 — Code Parsing

Planned tasks:

 Integrate Tree-sitter
 Parse supported languages
 Extract AST information
 Extract functions
 Extract classes
 Extract methods
 Extract imports
 Extract interfaces
 Store code symbols
Phase 5 — Dependency Analysis

Planned tasks:

 Build symbol relationships
 Detect function calls
 Detect imports
 Detect inheritance
 Build dependency graph
 Store dependency relationships
 Implement graph traversal
Phase 6 — Code Chunking

Planned tasks:

 Design semantic chunking strategy
 Chunk source code by meaningful structures
 Preserve file and symbol metadata
 Store chunk information
 Handle large files
Phase 7 — Embeddings & Retrieval

Planned tasks:

 Select embedding model
 Generate code embeddings
 Store embeddings
 Implement vector search
 Implement semantic retrieval
 Add metadata filtering
 Evaluate retrieval quality
Phase 8 — RAG Codebase Q&A

Planned tasks:

 Implement query processing
 Retrieve relevant code
 Retrieve dependency context
 Construct LLM context
 Generate responses
 Display source references
 Add conversational history
Phase 9 — Impact Analysis

Planned tasks:

 Accept a target symbol or file
 Traverse dependency relationships
 Identify direct dependents
 Identify indirect dependents
 Rank potential impact
 Generate human-readable impact reports
Phase 10 — AI Test Generation

Planned tasks:

 Analyze target functions
 Inspect existing tests
 Identify edge cases
 Generate test cases
 Follow repository testing conventions
 Display generated tests
 Allow developers to review generated tests
🔐 Security Considerations

CodeLens may eventually process private repositories and sensitive source code.

Security will therefore be an important part of the architecture.

Planned considerations include:

Never commit API keys
Store secrets in environment variables
Avoid exposing repository credentials
Restrict repository access
Validate GitHub tokens
Protect API endpoints
Avoid logging sensitive source code
Secure stored repository metadata
Control access to indexed repositories
📊 Long-Term Vision

The long-term goal is to make CodeLens function as an intelligent assistant for understanding software systems.

Instead of manually navigating through a repository, developers should be able to ask:

"How does authentication work?"
"What happens when a user places an order?"
"Which files will be affected if I change UserService?"
"Where is this API endpoint implemented?"
"Why is this function being called?"
"Generate tests for this function."

CodeLens should answer these questions using the actual structure and content of the repository rather than relying solely on general LLM knowledge.

🎓 Learning Goals

Building CodeLens provides practical experience with:

Full-stack development
REST APIs
FastAPI
React
TypeScript
PostgreSQL
Database design
GitHub APIs
Source-code parsing
ASTs
Tree-sitter
Dependency graphs
Graph traversal
Code chunking
Embeddings
Vector search
Retrieval-Augmented Generation
LLM applications
Prompt engineering
AI-assisted code analysis
Automated test generation
Software architecture
🤝 Development Philosophy

CodeLens is being developed incrementally.

Each major component is implemented, tested, and understood before moving to the next layer.

The project intentionally avoids implementing the entire AI architecture at once.

The development progression is:

Foundation
    ↓
Database
    ↓
Repository Ingestion
    ↓
Code Parsing
    ↓
AST & Symbols
    ↓
Dependencies
    ↓
Chunking
    ↓
Embeddings
    ↓
Retrieval
    ↓
RAG
    ↓
LLM Reasoning
    ↓
Impact Analysis
    ↓
Test Generation

This approach keeps the system easier to debug, test, understand, and explain.

📄 License

License information will be added as the project progresses.