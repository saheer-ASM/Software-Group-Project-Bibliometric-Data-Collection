require('dotenv').config();
const express = require('express');
const cors = require('cors');
const authRoutes   = require('./routes/auth');
const authorRoutes = require('./routes/authors');
const searchRoutes = require('./routes/search');

const app = express();

app.use(
  cors({
    origin(origin, callback) {
      if (!origin || /^http:\/\/localhost:\d+$/.test(origin)) {
        return callback(null, true);
      }

      return callback(new Error('Not allowed by CORS'));
    },
    credentials: true,
  })
);
app.use(express.json());

app.use('/api/auth',    authRoutes);
app.use('/api/authors', authorRoutes);
app.use('/api/search',  searchRoutes);

app.get('/api/health', (req, res) => res.json({ status: 'ok' }));

const PORT = process.env.PORT || 5000;
app.listen(PORT, 'localhost', () => console.log(`Server running on http://localhost:${PORT}`));
