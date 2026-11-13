// F5 AS3 pipeline: lint -> render -> validate -> (approval) -> deploy
// Jenkins credentials needed for deploy:
//   ansible-vault-pass  (type: Secret file) containing the vault password
pipeline {
    agent any

    parameters {
        booleanParam(name: 'DEPLOY', defaultValue: false,
                     description: 'Push the declaration to the BIG-IP after approval')
    }

    environment {
        VENV = "${WORKSPACE}/.venv"
        ANSIBLE_FORCE_COLOR = 'true'
    }

    stages {
        stage('Setup') {
            steps {
                sh '''
                    python3 -m venv "$VENV"
                    . "$VENV/bin/activate"
                    pip install -q -r requirements.txt
                '''
            }
        }

        stage('Lint') {
            steps {
                sh '. "$VENV/bin/activate" && ansible-lint playbooks/ roles/'
            }
        }

        stage('Render & Validate') {
            steps {
                sh '. "$VENV/bin/activate" && ansible-playbook playbooks/site.yml'
                archiveArtifacts artifacts: 'build/as3_*.json', fingerprint: true
            }
        }

        stage('Approval') {
            when { expression { params.DEPLOY } }
            steps {
                input message: 'Rendered declaration is archived above. Deploy to BIG-IP?',
                      ok: 'Deploy'
            }
        }

        stage('Deploy') {
            when { expression { params.DEPLOY } }
            steps {
                withCredentials([file(credentialsId: 'ansible-vault-pass', variable: 'VAULT_PASS_FILE')]) {
                    sh '''
                        . "$VENV/bin/activate"
                        ansible-playbook playbooks/site.yml \
                            -e as3_deploy=true \
                            --vault-password-file "$VAULT_PASS_FILE"
                    '''
                }
            }
        }
    }

    post {
        always {
            archiveArtifacts artifacts: 'build/*.json', allowEmptyArchive: true
        }
    }
}
