// Replace the article title block with the résumé's name and contact header.
#set document(title: [$title$], author: "Ron Medina")
#set text(font: "$mainfont$", size: $fontsize$)
#set par(justify: true, leading: 5.06pt, spacing: 5pt)
#set list(
  marker: box(width: 8pt, align(center, circle(radius: 1.8pt, fill: rgb("e95420")))),
  indent: 0pt,
  body-indent: 3pt,
  spacing: 5.06pt,
)
#show list: set block(above: 3pt, below: 0pt)
#show list.item: set block(breakable: false)
#show link: set text(fill: black)
#show heading.where(level: 2): it => block(
  width: 100%, above: 13pt, below: 10pt, sticky: true,
  stack(
    dir: ttb, spacing: 3pt,
    text(size: 14pt, weight: "bold", it.body),
    line(length: 100%, stroke: 0.35pt + rgb("555555")),
  ),
)
#show heading.where(level: 3): set text(size: 11pt, weight: "bold")
#show heading.where(level: 3): set block(above: 0pt, below: 0pt)

#let resume-entry(title, dates: [], date-size: 11pt) = block(
  width: 100%, above: 15pt, below: 7pt, sticky: true,
)[
  #set par(justify: false)
  #grid(
    columns: (1fr, auto), column-gutter: 10pt, align: (left, right),
    heading(level: 3, title),
    text(size: date-size, weight: "bold", dates),
  )
]

// Font Awesome is bundled with Quarto; the name and body fonts live in Atlas.
#let resume-icon(glyph, brands: false, regular: false) = box(
  width: 10pt,
  text(font: if brands { "Font Awesome 6 Brands" } else if regular {
    "Font Awesome 6 Free"
  } else { "Font Awesome 6 Free Solid" }, glyph),
)
#let contact-separator = box(inset: (x: 10pt), move(dy: -2.5pt, circle(radius: 1pt, fill: rgb("808080"))))
#let resume-header() = block(width: 100%, above: 0pt, below: 0pt)[
  #set align(center)
  #set par(justify: false, leading: 3pt, spacing: 0pt)
  #text(font: "Ubuntu", weight: "bold", size: 24.9pt, tracking: -0.045em, fill: rgb("343a40"))[
    Ron Medina#text(fill: rgb("e95420"))[.]
  ]
  #v(3pt)
  #text(size: 11pt, fill: rgb("808080"))[
    #show link: set text(fill: rgb("808080"))
    #link("tel:+639628316730")[#resume-icon("\u{f3cd}") (+63) 962 831 6730]
    #contact-separator
    #link("mailto:ron.mdn@gmail.com")[#resume-icon("\u{f0e0}", regular: true) ron.mdn\@gmail.com]
    #linebreak()
    #link("https://linkedin.com/in/ron-medina-5a411218a/")[#resume-icon("\u{f57d}") linkedin.com/in/ron-medina-5a411218a/]
    #contact-separator
    #link("https://github.com/particle1331")[#resume-icon("\u{f09b}", brands: true) particle1331]
  ]
]
