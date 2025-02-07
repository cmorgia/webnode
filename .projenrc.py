from projen.awscdk import AwsCdkPythonApp

project = AwsCdkPythonApp(
    author_email="claudio.morgia@sonarsource.com",
    author_name="Claudio Morgia",
    cdk_version="2.1.0",
    module_name="webnode",
    name="webnode",
    poetry=True,
    python_exec="python3",
    version="0.1.0",
)

project.synth()