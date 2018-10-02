
class Line(object):

    def print(self) -> str:
        pass


class MetricValue(Line):

    def __init__(self, name, labels, value):
        self.name = name
        self.labels = labels
        self.value = value

    def output(self) -> str:
        if self.labels is None:
            labels_str = ""
        else:
            labels_str = ",".join([
                '{key}=\"{val}\"'.format(
                    key=key,
                    val=self.labels[key]
                ) for key in sorted(self.labels.keys())
            ])
            if labels_str:
                labels_str = "{" + labels_str + "}"
        return "%(name)s%(labels)s %(value)s" % dict(
            name=self.name,
            labels=labels_str,
            value=self.value
        )


class DocStringLine(Line):

    def __init__(self, name, type, documentation):
        self.doc = documentation
        self.name = name
        self.type = type

    def output(self):
        return "# HELP {name} {doc}\n# TYPE {name} {type}".format(
            doc=self.doc,
            name=self.name,
            type=self.type,
        )
