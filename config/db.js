const mongoose = require('mongoose');
const dotenv = require('dotenv');

dotenv.config(); // Load environment variables from .env file

const MONGODB_URI = process.env.MONGODB_URI;

const connectDB = async () => {
  try {
    await mongoose.connect(MONGODB_URI, {
      useNewUrlParser: true,
      useUnifiedTopology: true,
    });
    console.log('MongoDB Connected...');
    // Later, we can replace console.log with the logger
  } catch (err) {
    console.error(err.message);
    // Later, we can replace console.error with the logger
    process.exit(1); // Exit process with failure
  }
};

module.exports = connectDB;
