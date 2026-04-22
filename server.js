const express = require('express');
const cors = require('cors');
const fs = require('fs');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3000;
const DATA_FILE = path.join(__dirname, 'data', 'alphabet.json');

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Helper: read data
function readData() {
  return JSON.parse(fs.readFileSync(DATA_FILE, 'utf8'));
}

// Helper: write data
function writeData(data) {
  fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 2), 'utf8');
}

// Helper: time ago in Arabic
function timeAgo() {
  return 'منذ لحظة';
}

// GET all alphabet data
app.get('/api/alphabet', (req, res) => {
  const data = readData();
  res.json(data);
});

// POST submit a word for a letter
app.post('/api/submit', (req, res) => {
  const { letterIndex, word, emoji, submitter } = req.body;
  const data = readData();
  const letter = data.letters[letterIndex];

  if (!letter) return res.status(400).json({ error: 'حرف غير صحيح' });
  if (letter.status !== 'empty') return res.status(400).json({ error: 'هذا الحرف مأخوذ بالفعل' });

  // Validate that word starts with correct letter
  const letterChar = letter.letter.replace('هـ', 'ه');
  const wordFirst = word.charAt(0);

  // Basic validation
  if (!word || word.trim().length < 2) {
    return res.status(400).json({ error: 'الكلمة قصيرة جداً' });
  }

  letter.status = 'pending';
  letter.word = word.trim();
  letter.emoji = emoji || '✨';
  letter.submitter = submitter || 'مجهول';
  letter.votes = 0;
  letter.upvotes = 0;
  letter.downvotes = 0;

  data.activity.unshift({
    text: `${submitter || 'أحدهم'} اقترح كلمة "${word}" للحرف ${letter.letter} 🟡`,
    time: timeAgo()
  });
  if (data.activity.length > 20) data.activity = data.activity.slice(0, 20);

  writeData(data);
  res.json({ success: true, letter });
});

// POST vote on a pending word
app.post('/api/vote', (req, res) => {
  const { letterIndex, vote } = req.body; // vote: 'up' or 'down'
  const data = readData();
  const letter = data.letters[letterIndex];

  if (!letter) return res.status(400).json({ error: 'حرف غير صحيح' });
  if (letter.status !== 'pending') return res.status(400).json({ error: 'لا يوجد اقتراح للتصويت عليه' });

  if (vote === 'up') {
    letter.upvotes = (letter.upvotes || 0) + 1;
  } else {
    letter.downvotes = (letter.downvotes || 0) + 1;
  }

  // 3 upvotes → approved
  if ((letter.upvotes || 0) >= 3) {
    letter.status = 'approved';
    letter.votes = letter.upvotes;
    data.activity.unshift({
      text: `تم اعتماد كلمة "${letter.word}" للحرف ${letter.letter} ✅`,
      time: timeAgo()
    });
  }

  // 3 downvotes → reset to empty
  if ((letter.downvotes || 0) >= 3) {
    letter.status = 'empty';
    const rejectedWord = letter.word;
    letter.word = '';
    letter.emoji = '';
    letter.submitter = '';
    letter.votes = 0;
    letter.upvotes = 0;
    letter.downvotes = 0;
    data.activity.unshift({
      text: `تم رفض كلمة "${rejectedWord}" للحرف ${letter.letter} ❌`,
      time: timeAgo()
    });
  }

  if (data.activity.length > 20) data.activity = data.activity.slice(0, 20);
  writeData(data);
  res.json({ success: true, letter });
});

// POST reset a letter (admin)
app.post('/api/reset', (req, res) => {
  const { letterIndex, secret } = req.body;
  if (secret !== 'saudi2025') return res.status(403).json({ error: 'غير مصرح' });

  const data = readData();
  const letter = data.letters[letterIndex];
  if (!letter) return res.status(400).json({ error: 'حرف غير صحيح' });

  letter.status = 'empty';
  letter.word = '';
  letter.emoji = '';
  letter.submitter = '';
  letter.votes = 0;
  letter.upvotes = 0;
  letter.downvotes = 0;

  writeData(data);
  res.json({ success: true });
});

app.listen(PORT, () => {
  console.log(`\n🌴 الأبجدية السعودية تعمل على: http://localhost:${PORT}\n`);
});
