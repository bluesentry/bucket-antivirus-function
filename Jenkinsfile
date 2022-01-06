pipeline {
    agent {
        docker {
			alwaysPull true
			args "--user root:root"
			image "sre-tooling:1.0.0"
			label "worker"
			registryCredentialsId "ecr:us-east-1:Jenkins-AWS-Key"
			registryUrl "https://393224622068.dkr.ecr.us-east-1.amazonaws.com"
		}
    }
    options {
        ansiColor("xterm")
        buildDiscarder(logRotator(numToKeepStr: '15'))
    }
    parameters {
        choice(
            name: "ENV",
            choices: [
                "dev",
                "staging",
                "prod"
            ],
            description: "Env to deploy the scanner function to"
        )
        choice(
            name: "ACCOUNT",
            choices: [
                "direct",
                "cleardata"
            ],
            description: "AWS account to deploy the scanner function to"
        )
    }

    stages {
        stage ("build") {
            steps {
                sshagent(credentials : ["Jenkins-SSH"]) {
                    sh 'git clone "git@github.com:NavigatingCancer/bucket-antivirus-function.git" --single-branch --branch "SRE-3926-s3-clamscan-poc" "src"'
                    dir ("src"){
                        sh "make all"
                        sh "cp ./build/lambda.zip /tmp/lambda.zip"
                    }
                }
            }
        }
        stage ("deploy") {
            steps {
                dir("src/infrastructure/${env.ACCOUNT}/${env.ENV}/s3-clamscan"){
                    sh "terragrunt plan -out tg.plan"
                    sh "terragrunt apply tg.plan"
                }
            }
        }
    }
}
