const { prisma } = require('./db.js');
async function run() {
  console.log('Collection:', await prisma.collection.findFirst({where: {studentId: 187}}));
  console.log('GrowthPlan:', await prisma.growthPlan.findFirst({where: {studentId: 187}}));
  console.log('StudentStats:', await prisma.studentStats.findFirst({where: {studentId: 187}}));
}
run().finally(() => prisma.$disconnect());
