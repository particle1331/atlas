-- Presentation only: the CMS still owns the entries and their authored Markdown.
local function typst(inlines)
  return pandoc.write(pandoc.Pandoc({ pandoc.Plain(inlines) }), "typst"):gsub("\n$", "")
end

local function unitalic(inlines)
  return pandoc.Span(inlines):walk({ Emph = function(el) return el.content end }).content
end

local function trim(inlines)
  while #inlines > 0 and pandoc.utils.stringify(inlines[1]):match("^[%s\194\160]*$") do
    inlines:remove(1)
  end
  while #inlines > 0 and pandoc.utils.stringify(inlines[#inlines]):match("^[%s\194\160]*$") do
    inlines:remove(#inlines)
  end
  return inlines
end

local function entry(header, dates, section)
  local title = header.content
  if section == "Employment History" then
    title = pandoc.Span(title):walk({ Str = function(el)
      if el.text == "·" then return pandoc.Str("|") end
    end }).content
  end
  local date_size = section == "Education" and ", date-size: 10pt" or ""
  local rendered = "#resume-entry([" .. typst(title) .. "], dates: ["
    .. typst(dates) .. "]" .. date_size .. ")"
  return pandoc.RawBlock("typst", rendered)
end

function Pandoc(doc)
  if not FORMAT:match("typst") then return doc end
  local output, early = pandoc.Blocks({}), pandoc.Blocks({})
  local section, roles, deferred = "", 0, false
  local configured_limit = doc.meta["resume-pdf-main-roles"]
  local limit = configured_limit
    and tonumber(pandoc.utils.stringify(configured_limit)) or math.huge
  local i = 1
  while i <= #doc.blocks do
    local block = doc.blocks[i]
    if block.t == "Header" and block.level == 2 then
      section = pandoc.utils.stringify(block.content)
      deferred = false
      if section == "Skills" and roles > 0 then
        output:insert(pandoc.RawBlock("typst", "#pagebreak(weak: true)"))
      end
    elseif block.t == "Header" and block.level == 3 and section == "Employment History" then
      roles = roles + 1
      deferred = roles > limit
    end
    local target = deferred and early or output
    if block.t == "Header" and block.level == 3 then
      local subtitle = doc.blocks[i + 1]
      local dates = pandoc.Inlines({})
      if subtitle and subtitle.t == "Div" and subtitle.classes:includes("resume-subtitle")
          and #subtitle.content == 1 and subtitle.content[1].t == "Para" then
        local paragraph = subtitle.content[1]
        local content = unitalic(paragraph.content)
        if section == "Employment History" then
          dates = content
          i = i + 1
        elseif section == "Education" then
          for j, inline in ipairs(content) do
            if inline.t == "Str" and inline.text == "·" then
              dates = trim(pandoc.Inlines({ table.unpack(content, j + 1) }))
              paragraph.content = trim(pandoc.Inlines({ table.unpack(content, 1, j - 1) }))
              break
            end
          end
        end
      end
      target:insert(entry(block, dates, section))
    elseif section == "Skills" and block.t == "Para"
        and #block.content == 1 and block.content[1].t == "Strong" then
      target:insert(entry(pandoc.Header(3, block.content[1].content), pandoc.Inlines({}), section))
    else
      target:insert(block)
    end
    i = i + 1
  end
  if #early > 0 then
    output:insert(pandoc.Header(2, "Early Employment"))
    output:extend(early)
  end
  doc.blocks = output
  return doc
end
