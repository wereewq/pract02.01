-- Скрипт инициализации базы данных ИС «КнигоГрад: Система учёта продаж и поставок»
CREATE DATABASE knigograd_db;

CREATE TABLE Users (
    ID_user SERIAL PRIMARY KEY,
    Login VARCHAR(50) UNIQUE NOT NULL,
    PasswordHash TEXT NOT NULL,
    FullName VARCHAR(150) NOT NULL,
    Role VARCHAR(20) NOT NULL CHECK (Role IN ('Администратор', 'Менеджер', 'Кассир', 'Руководитель'))
);

CREATE TABLE Stores (
    ID_Stores SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    Address VARCHAR(200) NOT NULL
);

CREATE TABLE Product (
    ID_product SERIAL PRIMARY KEY,
    Title VARCHAR(200) NOT NULL,
    Author VARCHAR(150) NOT NULL,
    Category VARCHAR(100) NOT NULL,
    Price DECIMAL(10,2) NOT NULL CHECK (Price > 0),
    ISBN VARCHAR(20) UNIQUE NOT NULL
);

CREATE TABLE Stock (
    ID_stock SERIAL PRIMARY KEY,
    Product_ID INT NOT NULL REFERENCES Product(ID_product) ON DELETE CASCADE,
    Store_ID INT NOT NULL REFERENCES Stores(ID_Stores) ON DELETE CASCADE,
    Quantity INT NOT NULL DEFAULT 0 CHECK (Quantity >= 0),
    UNIQUE (Product_ID, Store_ID)
);

CREATE TABLE Suppliers (
    ID_supplier SERIAL PRIMARY KEY,
    Name VARCHAR(150) NOT NULL,
    ContactName VARCHAR(100),
    Phone VARCHAR(20) NOT NULL,
    Email VARCHAR(100),
    Address VARCHAR(200)
);

CREATE TABLE Supplies (
    ID_supply SERIAL PRIMARY KEY,
    Supplier_ID INT NOT NULL REFERENCES Suppliers(ID_supplier),
    Store_ID INT NOT NULL REFERENCES Stores(ID_Stores),
    SupplyDate DATE NOT NULL DEFAULT CURRENT_DATE,
    InvoiceNumber VARCHAR(30) NOT NULL,
    TotalAmount DECIMAL(12,2) NOT NULL DEFAULT 0
);

CREATE TABLE Supply_Items (
    ID_supply_item SERIAL PRIMARY KEY,
    Supply_ID INT NOT NULL REFERENCES Supplies(ID_supply) ON DELETE CASCADE,
    Product_ID INT NOT NULL REFERENCES Product(ID_product),
    Quantity INT NOT NULL CHECK (Quantity > 0),
    PurchasePrice DECIMAL(10,2) NOT NULL CHECK (PurchasePrice > 0)
);

CREATE TABLE Customers (
    ID_customer SERIAL PRIMARY KEY,
    FullName VARCHAR(150) NOT NULL,
    Phone VARCHAR(20) NOT NULL,
    Email VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE Discount_Cards (
    ID_Discount_Cards SERIAL PRIMARY KEY,
    Customer_ID INT NOT NULL REFERENCES Customers(ID_customer) ON DELETE CASCADE,
    CardNumber VARCHAR(20) UNIQUE NOT NULL,
    DiscountPercent INT NOT NULL CHECK (DiscountPercent BETWEEN 0 AND 50),
    IssueDate DATE NOT NULL DEFAULT CURRENT_DATE,
    ValidUntil DATE
);

CREATE TABLE Sales (
    ID_sales SERIAL PRIMARY KEY,
    Date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    User_ID INT NOT NULL REFERENCES Users(ID_user),
    Store_ID INT NOT NULL REFERENCES Stores(ID_Stores),
    Customer_ID INT REFERENCES Customers(ID_customer),
    PaymentMethod VARCHAR(20) NOT NULL DEFAULT 'Карта',
    Status VARCHAR(20) NOT NULL DEFAULT 'Проведено',
    Total DECIMAL(12,2) NOT NULL CHECK (Total >= 0)
);

CREATE TABLE Sales_Items (
    ID_Sale_Items SERIAL PRIMARY KEY,
    Sale_ID INT NOT NULL REFERENCES Sales(ID_sales) ON DELETE CASCADE,
    Product_ID INT NOT NULL REFERENCES Product(ID_product),
    Quantity INT NOT NULL CHECK (Quantity > 0),
    PriceAtSale DECIMAL(10,2) NOT NULL,
    DiscountPercent INT NOT NULL DEFAULT 0
);
