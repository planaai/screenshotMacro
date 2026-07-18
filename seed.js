const { prisma } = require('./db.js');
const fs = require('fs');
const path = require('path');

async function main() {
  const dataPath = path.join(__dirname, 'data', 'plana_mapped.json');
  const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
  
  console.log('Loaded ' + data.length + ' students from plana_mapped.json');
  
  for (const s of data) {
    try {
      let squadType = s.fieldType === 'Striker' ? 'Main' : 'Support';
      if (s.fieldType !== 'Striker' && s.fieldType !== 'Special') { squadType = 'Main'; }
      
      let tacticRole = s.Role;
      if (!['DamageDealer', 'Tanker', 'Healer', 'Supporter', 'Ride'].includes(tacticRole)) {
         tacticRole = 'DamageDealer';
      }
      
      let bulletType = s.attackType;
      if (!['Explosion', 'Pierce', 'Mystic', 'Vibration', 'Decomposition'].includes(bulletType)) {
         bulletType = 'Explosion';
      }
      
      let armorType = s.armorType;
      if (!['LightArmor', 'HeavyArmor', 'MysticArmor', 'ElasticArmor', 'CompositeArmor'].includes(armorType)) {
         armorType = 'LightArmor';
      }
      
      let weaponType = s.weaponType;
      if (!['AR', 'SR', 'SG', 'SMG', 'MG', 'HG', 'GL', 'RL', 'MT', 'RG', 'FT'].includes(weaponType)) {
         weaponType = 'AR';
      }
      
      let position = s.position;
      if (!['Front', 'Middle', 'Back'].includes(position)) {
         position = 'Middle';
      }
      
      await prisma.student.upsert({
        where: { id: s.id },
        update: {
          name: s.name,
          school: s.school || 'Unknown',
          squadType: squadType,
          tacticRole: tacticRole,
          bulletType: bulletType,
          armorType: armorType,
          weaponType: weaponType,
          position: position,
          starGrade: s.starNum || 1,
          isLimited: s.isLimited || false
        },
        create: {
          id: s.id,
          name: s.name,
          school: s.school || 'Unknown',
          squadType: squadType,
          tacticRole: tacticRole,
          bulletType: bulletType,
          armorType: armorType,
          weaponType: weaponType,
          position: position,
          starGrade: s.starNum || 1,
          isLimited: s.isLimited || false
        }
      });
    } catch (err) {
      console.error('Error for ' + s.name + ': ' + err.message);
    }
  }
  console.log('Seeding completed!');
}

main()
  .catch(e => {
    console.error(e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
