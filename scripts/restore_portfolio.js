const fs = require('fs');
const path = require('path');
const file = path.join(__dirname, '../public/data/portfolio.json');

let data = [];
try {
  if (fs.existsSync(file)) {
    data = JSON.parse(fs.readFileSync(file, 'utf8'));
  }
} catch (e) {}

const stocksToAdd = ['00878', '3231', '2330'];
for (const stock of stocksToAdd) {
  if (!data.find(d => d.id === stock)) {
    data.push({ id: stock, shares: 1000, buyPrice: 0 }); // Default values
  }
}

fs.writeFileSync(file, JSON.stringify(data, null, 2));
console.log('Restored: ', data);
