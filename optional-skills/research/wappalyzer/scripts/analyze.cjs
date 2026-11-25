// SPDX-License-Identifier: Apache-2.0
// Call a separately installed upstream engine without its Chromium driver.
const fs = require('node:fs')
const path = require('node:path')

function analyze(root, capture) {
  const engine = require(path.join(root, 'src/wappalyzer.js'))
  engine.setCategories(JSON.parse(fs.readFileSync(path.join(root, 'src/categories.json'), 'utf8')))
  const technologies = {}
  for (const file of fs.readdirSync(path.join(root, 'src/technologies')).sort()) {
    if (file.endsWith('.json')) {
      Object.assign(technologies, JSON.parse(fs.readFileSync(path.join(root, 'src/technologies', file), 'utf8')))
    }
  }
  engine.setTechnologies(technologies)
  const data = Object.fromEntries(
    ['url', 'html', 'text', 'meta', 'scriptSrc', 'scripts'].map(key => [key, capture[key]])
  )
  const detections = engine.analyze(data)
  const activated = new Set()
  let resolved = engine.resolve(detections)
  // Conditional fingerprints only run once their required technology/category exists.
  while (true) {
    const names = new Set(resolved.map(technology => technology.name))
    const categories = new Set(resolved.flatMap(technology => technology.categories.map(category => category.id)))
    const eligible = [
      ...engine.requires.filter(group => names.has(group.name)),
      ...engine.categoryRequires.filter(group => categories.has(Number(group.id)))
    ].flatMap(group => group.technologies).filter(technology => !activated.has(technology.name))
    if (!eligible.length) break
    for (const technology of eligible) activated.add(technology.name)
    detections.push(...engine.analyze(data, eligible))
    resolved = engine.resolve(detections)
  }
  return { technologies: resolved.map(technology => ({
    ...technology,
    basis: detections.some(detection => detection.technology.name === technology.name) ? 'matched' : 'implied',
    signals: [...new Set(detections.filter(detection => detection.technology.name === technology.name)
      .map(detection => detection.pattern.type))]
  })) }
}

if (require.main === module) {
  try {
    const capture = JSON.parse(fs.readFileSync(0, 'utf8'))
    console.log(JSON.stringify(analyze(path.resolve(process.argv[2]), capture)))
  } catch (error) {
    console.error(error.message)
    process.exitCode = 1
  }
}

module.exports = { analyze }
