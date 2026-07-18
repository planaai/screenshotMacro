const express = require('express');
const router = express.Router();
const fs = require('fs');
const path = require('path');

let studentMasterDB = [];
try {
  studentMasterDB = JSON.parse(fs.readFileSync(path.join(__dirname, '../data/plana_mapped.json'), 'utf8'));
} catch (e) {
  console.log('Failed to load plana_mapped.json in studentsRouter', e.message);
}

// GET /api/students/names
router.get('/names', (req, res) => {
  res.json(studentMasterDB.map(s => s.name));
});

// GET /api/students
router.get('/', (req, res) => {
  res.json(studentMasterDB);
});

module.exports = router;
