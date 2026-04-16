"""
Forms for the CodeMap Analyzer.
"""
from django import forms

from .models import Project


# Component choices for the analysis filter
COMPONENT_CHOICES = [
    # Documentation
    ('overview', 'Project Overview'),
    ('architecture', 'Architecture Analysis'),
    ('workflow', 'Workflow & Logic'),
    ('user_manual', 'User Manual'),
    # UML Structural Diagrams
    ('class_diagram', 'Class Diagram'),
    ('object_diagram', 'Object Diagram'),
    ('component_diagram', 'Component Diagram'),
    ('composite_structure_diagram', 'Composite Structure Diagram'),
    ('package_diagram', 'Package Diagram'),
    ('deployment_diagram', 'Deployment Diagram'),
    ('profile_diagram', 'Profile Diagram'),
    # UML Behavioral Diagrams
    ('usecase_diagram', 'Use Case Diagram'),
    ('activity_diagram', 'Activity Diagram'),
    ('state_diagram', 'State Machine Diagram'),
    ('sequence_diagram', 'Sequence Diagram'),
    ('communication_diagram', 'Communication Diagram'),
    ('interaction_overview_diagram', 'Interaction Overview Diagram'),
    ('timing_diagram', 'Timing Diagram'),
    # Non-UML Diagrams
    ('er_diagram', 'ER Diagram (ERD)'),
    ('c4_context_diagram', 'C4 System Context'),
    ('workflow_flowchart', 'Workflow Flowchart'),
    ('mindmap', 'Mind Map'),
    ('project_structure', 'Project Structure'),
]

# All component values for default-all behavior
ALL_COMPONENT_VALUES = [c[0] for c in COMPONENT_CHOICES]


class ProjectUploadForm(forms.Form):
    """
    Form for uploading a project for analysis.

    Supports two modes:
    - ZIP file upload
    - Git repository URL

    Includes a component filter to select which outputs to generate.
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
    components = forms.MultipleChoiceField(
        choices=COMPONENT_CHOICES,
        initial=ALL_COMPONENT_VALUES,
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'component-checkbox',
        }),
        help_text='Select which outputs to generate. All selected by default.',
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
                name = zip_file.name.rsplit('.', 1)[0]
                cleaned_data['project_name'] = name
            elif upload_type == 'git' and git_url:
                name = git_url.rstrip('/').rsplit('/', 1)[-1]
                if name.endswith('.git'):
                    name = name[:-4]
                cleaned_data['project_name'] = name

        # Default components to all if none selected
        if not cleaned_data.get('components'):
            cleaned_data['components'] = ALL_COMPONENT_VALUES

        return cleaned_data
        
from .models import UserProfile

class UserProfileForm(forms.ModelForm):
    company_name = forms.CharField(
        max_length=255, 
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter Company Name'})
    )
    company_logo = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'file-input', 'accept': 'image/*'})
    )

    class Meta:
        model = UserProfile
        fields = ['company_name', 'company_logo']


class PDFSettingsForm(forms.ModelForm):
    logo_position = forms.ChoiceField(
        choices=UserProfile.LOGO_POSITION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-input', 'id': 'id_logo_position'})
    )
    logo_size = forms.IntegerField(
        required=False, initial=60, min_value=20, max_value=200,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'id': 'id_logo_size'})
    )
    name_size = forms.IntegerField(
        required=False, initial=28, min_value=12, max_value=72,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'id': 'id_name_size'})
    )
    header_color = forms.CharField(
        max_length=7, required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'type': 'color', 'id': 'id_header_color'})
    )
    header_title = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Project Analysis Report', 'id': 'id_header_title'})
    )
    header_subtitle = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Comprehensive Documentation & Architecture Report', 'id': 'id_header_subtitle'})
    )
    footer_text = forms.CharField(
        max_length=255, required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Leave blank to use company name', 'id': 'id_footer_text'})
    )
    show_page_numbers = forms.BooleanField(
        required=False, initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'id_show_page_numbers'})
    )
    body_font_size = forms.IntegerField(
        required=False, initial=11, min_value=8, max_value=16,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'id': 'id_body_font_size'})
    )
    heading_font_size = forms.IntegerField(
        required=False, initial=18, min_value=12, max_value=36,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'id': 'id_heading_font_size'})
    )

    class Meta:
        model = UserProfile
        fields = [
            'logo_position', 'logo_size', 'name_size',
            'header_color', 'header_title', 'header_subtitle',
            'footer_text', 'show_page_numbers',
            'body_font_size', 'heading_font_size',
        ]
