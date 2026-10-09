"""Load components via explicit services without relying on ros2 CLI daemon state."""
import rclpy
from rclpy.parameter import Parameter
from composition_interfaces.srv import LoadNode


def load_component(observer, container, plugin, parameters, name):
    client = observer.create_client(LoadNode, f"/{container}/_container/load_node")
    try:
        if not client.wait_for_service(timeout_sec=20):
            raise TimeoutError("Component service unavailable; check the selected RMW")
        request = LoadNode.Request(package_name="vins", plugin_name=plugin, node_name=name)
        request.parameters = [Parameter(key, value=value).to_parameter_msg() for key, value in parameters.items()]
        request.extra_arguments = [Parameter("use_intra_process_comms", value=True).to_parameter_msg()]
        future = client.call_async(request)
        rclpy.spin_until_future_complete(observer, future, timeout_sec=30)
        if not future.done():
            raise TimeoutError("Component load timed out")
        response = future.result()
        if not response.success:
            raise RuntimeError(response.error_message)
        return response.unique_id
    finally:
        observer.destroy_client(client)
