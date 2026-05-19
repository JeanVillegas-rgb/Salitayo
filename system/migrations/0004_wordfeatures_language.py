from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("system", "0003_alter_flaggedword_type_alter_passage_user_sessionlog_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="wordfeatures",
            name="language",
            field=models.CharField(
                choices=[("en", "English"), ("fil", "Filipino")],
                default="en",
                max_length=8,
            ),
        ),
    ]
