from aws_cdk import (
    aws_codebuild as codebuild,
    aws_codepipeline as codepipeline,
    aws_codepipeline_actions as codepipeline_actions,
    aws_ecr as ecr,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as sfn_tasks,
)
import aws_cdk as cdk
from constructs import Construct
from webnode.aspects import IAMResourcePatcherAspect
import os

class MyStack(cdk.Stack):

    def __init__(self, scope: Construct, id: str, **kwargs) -> None:
        super().__init__(scope, id, **kwargs)

        ecr_repo = ecr.Repository(self, 'webnodets-repo',
                                  repository_name='webnodets-repo',
                                  removal_policy=cdk.RemovalPolicy.DESTROY)

        srv = ecs_patterns.ApplicationLoadBalancedFargateService(self, 'webnodets-service',
                                                                 task_image_options={
                                                                     'image': ecs.ContainerImage.from_ecr_repository(ecr_repo),
                                                                     'container_name': 'webnodets-service',
                                                                 })

        pipeline = codepipeline.Pipeline(self, 'webnodets-pipeline',
                                         pipeline_name='webnodets-pipeline')

        source_output = codepipeline.Artifact()
        build_output = codepipeline.Artifact('BuildOutput')

        pipeline.add_stage(stage_name='Source',
                           actions=[
                               codepipeline_actions.EcrSourceAction(
                                   action_name='EcrSource',
                                   repository=ecr_repo,
                                   output=source_output,
                               ),
                           ])

        build_project = codebuild.PipelineProject(self, 'BuildProject',
                                                  build_spec=codebuild.BuildSpec.from_object({
                                                      'version': '0.2',
                                                      'phases': {
                                                          'build': {
                                                              'commands': [
                                                                  'echo "[{\\"name\\":\\"webnodets-service\\",\\"imageUri\\":\\"$REPOSITORY_URI:latest\\"}]" > imagedefinitions.json'
                                                              ],
                                                          },
                                                      },
                                                      'artifacts': {
                                                          'files': 'imagedefinitions.json',
                                                      },
                                                  }),
                                                  environment_variables={
                                                      'REPOSITORY_URI': codebuild.BuildEnvironmentVariable(
                                                          value=ecr_repo.repository_uri
                                                      ),
                                                  })

        pipeline.add_stage(stage_name='Build',
                           actions=[
                               codepipeline_actions.CodeBuildAction(
                                   action_name='CodeBuild',
                                   project=build_project,
                                   input=source_output,
                                   outputs=[build_output],
                               ),
                           ])

        run_task = sfn_tasks.EcsRunTask(self, 'RunFargate',
                                        integration_pattern=sfn.IntegrationPattern.RUN_JOB,
                                        cluster=srv.cluster,
                                        task_definition=srv.task_definition,
                                        assign_public_ip=True,
                                        container_overrides=[{
                                            'containerDefinition': srv.task_definition.default_container,
                                            'environment': [{'name': 'WORKER_TYPE', 'value': "leader"}],
                                        }],
                                        launch_target=sfn_tasks.EcsFargateLaunchTarget(platform_version=ecs.FargatePlatformVersion.VERSION1_4),
                                        propagated_tag_source=ecs.PropagatedTagSource.TASK_DEFINITION)

        state_machine = sfn.StateMachine(self, 'StateMachine',
                                         definition=run_task)

        pipeline.add_stage(stage_name='RunTask',
                           actions=[
                               codepipeline_actions.StepFunctionInvokeAction(
                                   action_name='InvokeStepFunction',
                                   state_machine=state_machine,
                               ),
                           ])

        pipeline.add_stage(stage_name='Deploy',
                           actions=[
                               codepipeline_actions.EcsDeployAction(
                                   action_name='DeployAction',
                                   service=srv.service,
                                   input=build_output,
                               ),
                           ])

        cdk.CfnOutput(self, 'LoadBalancerDNS',
                       value=f"http://{srv.load_balancer.load_balancer_dns_name}")


app = cdk.App()
cdk.Aspects.of(app).add(IAMResourcePatcherAspect())
dev_env = {
    'account': os.getenv('CDK_DEFAULT_ACCOUNT'),
    'region': os.getenv('CDK_DEFAULT_REGION'),
}

MyStack(app, 'webnodets-dev', env=dev_env)
# MyStack(app, 'webnodets-prod', env=prod_env)

app.synth()