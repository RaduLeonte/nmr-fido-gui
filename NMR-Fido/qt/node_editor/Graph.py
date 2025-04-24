
from qt.node_editor.Wire import Wire

class Graph:
    def __init__(self):
        self.nodes = []
        self.connections = []

    def add_node(self, node):
        self.nodes.append(node)

    def connect(self, output_widget, input_widget) -> None:
        output_port = output_widget.port  # This must be a Port (inherits QGraphicsItem)
        input_port = input_widget.port    # Also a Port
        
        input_port.connected_port = output_port

        wire = Wire(output_port=output_port, input_port=input_port)
        
        if hasattr(input_widget, "on_connection_changed"):
            input_widget.on_connection_changed()
        
        return


    def disconnect(self, input_widget):
        if hasattr(input_widget, "port"):
            input_widget.port.connected_port = None
        if hasattr(input_widget, "on_connection_changed"):
            input_widget.on_connection_changed()
        

    def evaluate(self, node, cache=None):
        if cache is None:
            cache = {}
        if node in cache:
            return cache[node]

        inputs = node.prepare_inputs(self, cache)
        result = node.compute(inputs)
        cache[node] = result
        return result