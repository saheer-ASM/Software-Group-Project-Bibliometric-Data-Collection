const authorRepo  = require('../repositories/authorRepository');

async function searchByName(name) {
  const authors = await authorRepo.findByName(name);
  return authors;
}

module.exports = { searchByName };
