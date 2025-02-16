import jsii
from aws_cdk import CfnResource, IAspect, Stack


@jsii.implements(IAspect)
class IAMResourcePatcherAspect:
    """
    An Aspect that patches IAM resources (roles, policies, and instance profiles) so that they
    conform to the new IAM permissions model.

    The IAM resources must satisfy the following requirements:
    - IAM roles must be placed under the `/approles/` path with a permissions boundary attached
        - AppPermissionsBoundary for application-like permissions
        - CustomResourcePermissionsBoundary for permissions required by custom resources
    - IAM policies must be placed under the "/apppolicies/" path
    - IAM instance profiles must be placed under the "/appinstanceprofiles/" path

    Note: In some cases, resources are added to the node tree as `aws_cdk.CfnResource` instances.
    To make sure we process all IAM resources, we check `if isinstance(node, aws_cdk.CfnResource)`
    instead of e.g., `if isinstance(node, aws_iam.CfnRole)`.

    :param cr_role_ids: A list of IAM role logical IDs created by custom resource(s) that will be
    placed under the "/approles/cr/" path with the CustomResourcePermissionsBoundary attached
    """

    def __init__(self, cr_role_ids: list[str] | None = None):
        super().__init__()
        self.cr_role_ids = [] if cr_role_ids is None else cr_role_ids

    def visit(self, node) -> None:

        if isinstance(node, CfnResource) and node.cfn_resource_type == "AWS::IAM::Role":
            # Obtain the logical ID of the role, as the name is not available at synthesis time,
            # unless explicitly set in the CDK code
            logical_id: str = Stack.of(node).resolve(node.logical_id)
            account_id: str = Stack.of(node).account

            # IAM roles created by CustomResource(s) should be placed under the "/approles/cr/" path
            if any(role in logical_id for role in self.cr_role_ids):
                node.add_property_override("Path", "/approles/cr/")
                node.add_property_override(
                    "PermissionsBoundary",
                    f"arn:aws:iam::{account_id}:policy/CustomResourcePermissionsBoundary-V1",
                )

            # All other roles should be placed under the "/approles/" path
            else:
                node.add_property_override("Path", "/approles/")
                node.add_property_override(
                    "PermissionsBoundary",
                    f"arn:aws:iam::{account_id}:policy/AppPermissionsBoundary-V1",
                )

        if isinstance(node, CfnResource) and node.cfn_resource_type == "AWS::IAM::ManagedPolicy":
            node.add_property_override("Path", "/apppolicies/")

        if isinstance(node, CfnResource) and node.cfn_resource_type == "AWS::IAM::InstanceProfile":
            node.add_property_override("Path", "/appinstanceprofiles/")