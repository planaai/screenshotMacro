const fs = require('fs');
const path = '/var/www/planaaiWebsite/backend/routes/importRoute.js';
let content = fs.readFileSync(path, 'utf8');

const replacement = `    let detailsObj = existingCollection?.details ? (typeof existingCollection.details === 'string' ? JSON.parse(existingCollection.details) : existingCollection.details) : {};
    
    // frontend ArchiveRecord 형식에 맞게 데이터 저장
    detailsObj.level = currentLevel || detailsObj.level || 1;
    detailsObj.currentStars = currentStar || detailsObj.currentStars || 1;
    
    if (req.body.bondRank !== undefined && req.body.bondRank !== null) detailsObj.bondRank = req.body.bondRank;
    
    const parseSkillNum = (val, isEx) => {
      if (val === 'MAX' || val === 'max') return isEx ? 5 : 10;
      if (typeof val === 'string') {
        const match = val.match(/\\\\d+/);
        if (match) return parseInt(match[0]);
      }
      const num = parseInt(val);
      return isNaN(num) ? 1 : num;
    };

    detailsObj.skillLevels = detailsObj.skillLevels || { ex: 1, normal: 1, passive: 1, sub: 1 };
    if (skills) {
      if (skills.ex !== undefined) detailsObj.skillLevels.ex = parseSkillNum(skills.ex, true);
      if (skills.basic !== undefined) detailsObj.skillLevels.normal = parseSkillNum(skills.basic, false);
      if (skills.enh !== undefined) detailsObj.skillLevels.passive = parseSkillNum(skills.enh, false);
      if (skills.sub !== undefined) detailsObj.skillLevels.sub = parseSkillNum(skills.sub, false);
    }

    detailsObj.equipment = detailsObj.equipment || { slot1: null, slot2: null, slot3: null, slot4: null };
    if (equipment) {
      if (equipment.slot1) detailsObj.equipment.slot1 = { tier: parseInt(equipment.slot1.tier) || 1, level: parseInt(equipment.slot1.level) || 1 };
      if (equipment.slot2) detailsObj.equipment.slot2 = { tier: parseInt(equipment.slot2.tier) || 1, level: parseInt(equipment.slot2.level) || 1 };
      if (equipment.slot3) detailsObj.equipment.slot3 = { tier: parseInt(equipment.slot3.tier) || 1, level: parseInt(equipment.slot3.level) || 1 };
      if (equipment.slot4 && equipment.slot4.tier > 0) detailsObj.equipment.slot4 = { tier: parseInt(equipment.slot4.tier) || 1, level: parseInt(equipment.slot4.level) || 1 };
    }

    if (weapon && weapon.star > 0) {
      detailsObj.uniqueWeapon = { stars: weapon.star || 0, level: weapon.level || 1 };
    } else if (weapon && weapon.star === 0) {
      detailsObj.uniqueWeapon = null;
    }

    detailsObj.stats = detailsObj.stats || {};
    if (stats) {
      if (stats.maxHP !== undefined) detailsObj.stats.maxHP = stats.maxHP;
      if (stats.attackPower !== undefined) detailsObj.stats.attackPower = stats.attackPower;
      if (stats.defensePower !== undefined) detailsObj.stats.defensePower = stats.defensePower;
      if (stats.healPower !== undefined) detailsObj.stats.healPower = stats.healPower;
      
      // 능력개방 레벨 저장 (frontend의 potentialLevels 구조에 맞춤)
      if (stats.hpAbility !== undefined || stats.atkAbility !== undefined || stats.healAbility !== undefined) {
        if (!detailsObj.potentialLevels) detailsObj.potentialLevels = {};
        if (stats.hpAbility !== undefined) detailsObj.potentialLevels.maxHP = stats.hpAbility;
        if (stats.atkAbility !== undefined) detailsObj.potentialLevels.attackPower = stats.atkAbility;
        if (stats.healAbility !== undefined) detailsObj.potentialLevels.healPower = stats.healAbility;
      }
    }\`;

// Replace the block from 'let detailsObj = ' to 'await prisma.collection.upsert({'
const startIdx = content.indexOf('let detailsObj =');
const endIdx = content.indexOf('await prisma.collection.upsert({');

if (startIdx !== -1 && endIdx !== -1) {
  content = content.substring(0, startIdx) + replacement + '\n\n    ' + content.substring(endIdx);
  fs.writeFileSync(path, content, 'utf8');
  console.log('Successfully patched importRoute.js');
} else {
  console.log('Failed to find replacement markers');
}
