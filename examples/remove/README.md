# Remove template

`remove.csv` is a header-only template for `tgcli remove`: it names nothing, so a copy removes nothing until you add lines.

```csv
kind,id,name,network,address
group,,Contractors 2024,,
resource,,Wiki,HQ,wiki.internal
network,,Old Datacentre,,
```

- `kind`: `resource`, `group` or `network`.
- Give an `id`, a `name`, or both (then they must agree). A resource name that is used in more than one Remote Network can be narrowed with `network` and `address`.
- Always run it without `--execute` first and read the list: `tgcli -s <session> remove remove.csv`.
