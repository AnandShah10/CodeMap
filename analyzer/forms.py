"""
Forms for the CodeMap Analyzer.
"""
from django import forms

from .models import Project


class ProjectUploadForm(forms.Form):
    """
    Form for uploading a project for analysis.

    Supports two modes:
    - ZIP file upload
    - Git repository URL
    """

    UPLOAD_TYPE_CHOICES = [
        ('zip', 'Upload ZIP File'),
        ('git', 'Git Repository URL'),
    ]

    upload_type = forms.ChoiceField(
        choices=UPLOAD_TYPE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'upload-type-radio', 'id': 'upload-type'}),
        initial='zip',
    )
    project_name = forms.CharField(
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'id': 'project-name',
            'placeholder': 'e.g., My Awesome Project (auto-detected if empty)',
        }),
        help_text='Optional. Auto-derived from the filename or repo URL if left blank.',
    )
    zip_file = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(attrs={
            'class': 'file-input',
            'id': 'zip-file',
            'accept': '.zip',
        }),
        help_text='Upload a ZIP file of your project.',
    )
    git_url = forms.URLField(
        required=False,
        widget=forms.URLInput(attrs={
            'class': 'form-input',
            'id': 'git-url',
            'placeholder': 'https://github.com/user/repo.git',
        }),
        help_text='Enter the full URL of the Git repository.',
    )

    def clean(self):
        """Validate that the correct fields are provided based on upload type."""
        cleaned_data = super().clean()
        upload_type = cleaned_data.get('upload_type')
        zip_file = cleaned_data.get('zip_file')
        git_url = cleaned_data.get('git_url')

        if upload_type == 'zip':
            if not zip_file:
                self.add_error('zip_file', 'Please upload a ZIP file.')
            elif not zip_file.name.lower().endswith('.zip'):
                self.add_error('zip_file', 'Only ZIP files are accepted.')
        elif upload_type == 'git':
            if not git_url:
                self.add_error('git_url', 'Please enter a Git repository URL.')
            elif not (git_url.endswith('.git') or 'github.com' in git_url
                      or 'gitlab.com' in git_url or 'bitbucket.org' in git_url):
                self.add_error(
                    'git_url',
                    'Please enter a valid Git repository URL '
                    '(e.g., https://github.com/user/repo.git).'
                )

        # Auto-derive project name
        if not cleaned_data.get('project_name'):
            if upload_type == 'zip' and zip_file:
                # Remove .zip extension
                name = zip_file.name.rsplit('.', 1)[0]
                cleaned_data['project_name'] = name
            elif upload_type == 'git' and git_url:
                # Extract repo name from URL
                name = git_url.rstrip('/').rsplit('/', 1)[-1]
                if name.endswith('.git'):
                    name = name[:-4]
                cleaned_data['project_name'] = name

        return cleaned_data
