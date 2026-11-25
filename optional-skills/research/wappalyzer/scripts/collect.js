// SPDX-License-Identifier: Apache-2.0
// Evaluate this expression in the existing browser tool after navigation.
JSON.stringify({
  url: location.href,
  html: document.documentElement.outerHTML,
  text: document.body ? document.body.innerText : '',
  meta: Array.from(document.querySelectorAll('meta')).reduce((result, element) => {
    const key = element.getAttribute('name') || element.getAttribute('property')
    if (key) {
      const name = key.toLowerCase()
      ;(result[name] ||= []).push(element.getAttribute('content') || '')
    }
    return result
  }, {}),
  scriptSrc: Array.from(document.scripts, element => element.src).filter(Boolean),
  scripts: Array.from(document.scripts, element => element.src ? '' : element.textContent).filter(Boolean)
})
