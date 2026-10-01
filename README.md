# Commerce Core

RESTful e-commerce backend built with **FastAPI, PostgreSQL, SQLAlchemy, and Alembic**.

Commerce Core provides the backend foundation for an e-commerce application, including authentication, product and category management, shopping cart operations, orders, payments, and favorites.

---

## ✨ Features

- User authentication and authorization
- JWT-based authentication
- Product management
- Category management
- Shopping cart operations
- Order management
- Payment endpoints
- Favorite products
- PostgreSQL persistence
- Database migrations with Alembic
- Request validation with Pydantic
- CORS configuration
- Interactive API documentation
- Automated API testing support

---

## 🛠 Tech Stack

### Backend

- **Python**
- **FastAPI**
- **SQLAlchemy 2**
- **Pydantic**
- **Uvicorn**

### Database

- **PostgreSQL**
- **Alembic**
- **psycopg2**

### Authentication & Security

- **JWT**
- **python-jose**
- **Passlib**
- **bcrypt**

### Testing

- **Pytest**
- **HTTPX**

---

## 🏗 API Architecture

The application separates the API into dedicated domain routers.

```text
FastAPI Application
        │
        ├── Authentication
        ├── Categories
        ├── Products
        ├── Cart
        ├── Orders
        ├── Payments
        └── Favorites
                │
                ▼
           SQLAlchemy
                │
                ▼
           PostgreSQL
```

This structure keeps different business domains isolated while allowing them to share the same application infrastructure.

---

## 🔌 API Modules

| Module | Route | Responsibility |
| --- | --- | --- |
| Authentication | `/auth` | User authentication and authorization |
| Categories | `/categories` | Product category operations |
| Products | `/products` | Product management |
| Cart | `/cart` | Shopping cart operations |
| Orders | `/orders` | Order management |
| Payments | `/payments` | Payment-related operations |
| Favorites | `/favorites` | User favorite products |

---

## 📂 Project Structure

```text
commerce-core/
├── app/
│   ├── api/
│   │   └── endpoints/
│   │       ├── auth.py
│   │       ├── category.py
│   │       ├── product.py
│   │       ├── cart.py
│   │       ├── order.py
│   │       ├── payment.py
│   │       └── favorite.py
│   │
│   ├── core/
│   │   └── config.py
│   │
│   └── main.py
│
├── alembic/
├── alembic.ini
├── requirements.txt
└── ...
```

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/fatihemreyuce/commerce-core.git
cd commerce-core
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate the environment.

**Windows**

```bash
.venv\Scripts\activate
```

**Linux / macOS**

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file and configure the required application settings such as the database connection and authentication secrets.

> Never commit database credentials, JWT secrets, or other private configuration values.

### 5. Run database migrations

```bash
alembic upgrade head
```

### 6. Start the API

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://localhost:8000
```

---

## 📖 API Documentation

FastAPI automatically provides interactive API documentation.

### Swagger UI

```text
http://localhost:8000/docs
```

### ReDoc

```text
http://localhost:8000/redoc
```

These interfaces can be used to inspect and test the available API endpoints.

---

## 🧪 Testing

Run the test suite with:

```bash
pytest
```

---

## 🎯 Purpose

Commerce Core was created to practice and demonstrate backend architecture for a real-world e-commerce domain, including authentication, relational data modeling, API design, database migrations, and modular service development.

---

## 👤 Author

### Fatih Emre Yüce

**Software Engineering Student · Full-Stack Developer**

[GitHub](https://github.com/fatihemreyuce)
