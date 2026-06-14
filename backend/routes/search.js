const express = require('express');

const router = express.Router();

// Mock data for demonstration
const mockAuthors = {
  'john doe': {
    author: 'John Doe',
    email: 'john.doe@university.edu',
    totalPublications: 45,
    totalCitations: 320,
    totalSelfCitations: 28,
    nmIndex: 12,
    hIndex: 8,
    cScore: 2.85,
    trendData: [
      { name: 'P', publications: 200, citations: 240 },
      { name: 'Q', publications: 221, citations: 180 },
      { name: 'R', publications: 229, citations: 200 },
      { name: 'S', publications: 200, citations: 220 },
      { name: 'T', publications: 250, citations: 260 }
    ],
    publications: [
      {
        id: 1,
        title: 'Advanced Techniques in Machine Learning for Data Analysis',
        fields: ['Machine Learning', 'Data Science', 'AI', 'Analytics', 'Algorithms'],
        authors: ['Dr. Smith', 'Dr. Johnson', 'Dr. Williams'],
        selfCitations: 12,
        publishedYear: 2023,
        totalCitations: 45
      },
      {
        id: 2,
        title: 'Neural Network Applications in Healthcare Systems',
        fields: ['Neural Networks', 'Healthcare', 'Deep Learning', 'Medical AI', 'Systems'],
        authors: ['Dr. Brown', 'Dr. Davis', 'Dr. Miller'],
        selfCitations: 8,
        publishedYear: 2023,
        totalCitations: 62
      },
      {
        id: 3,
        title: 'Distributed Computing Frameworks for Big Data Processing',
        fields: ['Distributed Systems', 'Big Data', 'Cloud Computing', 'Frameworks', 'Scalability'],
        authors: ['Dr. Wilson', 'Dr. Taylor', 'Dr. Anderson'],
        selfCitations: 5,
        publishedYear: 2022,
        totalCitations: 38
      }
    ]
  },
  'jane smith': {
    author: 'Jane Smith',
    email: 'jane.smith@university.edu',
    totalPublications: 52,
    totalCitations: 487,
    totalSelfCitations: 42,
    nmIndex: 15,
    hIndex: 11,
    cScore: 3.2,
    trendData: [
      { name: 'P', publications: 180, citations: 200 },
      { name: 'Q', publications: 210, citations: 250 },
      { name: 'R', publications: 240, citations: 280 },
      { name: 'S', publications: 280, citations: 350 },
      { name: 'T', publications: 300, citations: 400 }
    ],
    publications: [
      {
        id: 1,
        title: 'Quantum Computing Applications in Cryptography',
        fields: ['Quantum Computing', 'Cryptography', 'Security', 'Algorithms', 'Theory'],
        authors: ['Dr. Johnson', 'Dr. Williams', 'Dr. Brown'],
        selfCitations: 15,
        publishedYear: 2023,
        totalCitations: 78
      },
      {
        id: 2,
        title: 'Blockchain Technology for Distributed Systems',
        fields: ['Blockchain', 'Distributed Systems', 'Cryptography', 'Technology', 'Security'],
        authors: ['Dr. Davis', 'Dr. Miller', 'Dr. Wilson'],
        selfCitations: 10,
        publishedYear: 2023,
        totalCitations: 95
      },
      {
        id: 3,
        title: 'Scalable Solutions for Enterprise Architecture',
        fields: ['Enterprise Architecture', 'Scalability', 'Systems Design', 'Software', 'Performance'],
        authors: ['Dr. Taylor', 'Dr. Anderson', 'Dr. Thompson'],
        selfCitations: 8,
        publishedYear: 2022,
        totalCitations: 72
      }
    ]
  }
};

// GET /api/search?author=name
router.get('/', (req, res) => {
  try {
    const { author } = req.query;

    if (!author) {
      return res.status(400).json({ message: 'Author name is required' });
    }

    const authorKey = author.toLowerCase().trim();
    const authorData = mockAuthors[authorKey];

    if (!authorData) {
      return res.status(404).json({ message: `Author "${author}" not found in database` });
    }

    res.json(authorData);
  } catch (err) {
    res.status(500).json({ message: 'Server error', error: err.message });
  }
});

module.exports = router;
