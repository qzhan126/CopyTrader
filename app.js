require('dotenv').config(); // Must be at the very top
const express = require('express');
const connectDB = require('./config/db');
const logger = require('./config/logger');
const tradeRoutes = require('./routes/tradeRoutes');
const { startScheduledJob } = require('./services/jobService');

// Initialize Express app
const app = express();

// Connect to Database
connectDB();

// Middleware
app.use(express.json()); // for parsing application/json
app.use(express.urlencoded({ extended: false })); // for parsing application/x-www-form-urlencoded

// HTTP Request Logger Middleware
// Placed before routes and after body parsing to have access to req.body if needed (but be cautious)
app.use((req, res, next) => {
  // Log basic info. Avoid logging sensitive body/query params in production without sanitization.
  logger.http(`${req.method} ${req.originalUrl}`, { 
    ip: req.ip,
    // Example of how you might selectively log parts of body/query in future:
    // query: JSON.stringify(req.query), // Stringify to ensure it's captured as a single field
    // bodyKeys: req.body ? Object.keys(req.body) : [] // Log only keys to know what was sent
  });
  next();
});

// Mount API routes
app.use('/api/trades', tradeRoutes);

// Simple root endpoint
app.get('/', (req, res) => {
  res.send('Binance Copy Trade Monitor Service is Healthy and Running');
});

// Start Scheduled Job
// This is a good place, after DB connection and before server listen.
// If jobService relied heavily on other routes or complex setup, might be later, but here it's fine.
startScheduledJob(); 

// Global Error Handling Middleware (must be the last piece of middleware)
app.use((err, req, res, next) => {
  logger.error('Unhandled Error:', { 
    message: err.message, 
    stack: err.stack, 
    url: req.originalUrl, 
    method: req.method,
    status: err.status // Include if error object has a status property
  });

  // If headers have already been sent to the client, delegate to the default Express error handler
  if (res.headersSent) {
    return next(err);
  }

  res.status(err.status || 500).json({
    message: err.message || 'Internal Server Error',
    // Optionally include stack in development mode for easier debugging
    stack: process.env.NODE_ENV === 'development' ? err.stack : undefined 
  });
});


// Start server
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  logger.info(`Server running on port ${PORT}`);
});
