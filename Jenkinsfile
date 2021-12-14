pipeline {
    agent { label "worker" }
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
                sh "make all"
                sh "cp ./build/lambda.zip /tmp/lambda.zip"
            }
        }
        stage ("deploy") {
            steps {
                dir("infrastructure/${env.ACCOUNT}/${env.ENV}/s3-clamscan"){
                    sh "terragrunt plan -out tg.plan"
                    sh "terragrunt apply tg.plan"
                }
            }
        }
    }
}
