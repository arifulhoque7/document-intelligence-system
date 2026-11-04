-- Separate database for the automated tests, so they never touch real data.
CREATE DATABASE docintel_test OWNER docintel;
\c docintel_test
CREATE EXTENSION IF NOT EXISTS vector;
\c docintel
CREATE EXTENSION IF NOT EXISTS vector;
